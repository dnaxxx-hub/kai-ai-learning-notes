"""Write-Ahead Log (WAL) — crash recovery via pre-write logging.

Layout: a single file. Each record:
  [magic: 4B][crc32: 4B][txn_id: 4B][type: 1B][data_len: 4B][data...]

Record types:
  0xB0 = BEGIN TRANSACTION
  0xB1 = COMMIT TRANSACTION
  0xB2 = ROLLBACK TRANSACTION
  0x10 = INSERT record (table_name, key, value as JSON)
  0x11 = DELETE record (table_name, key)
  0x12 = UPDATE record (table_name, key, new_value as JSON)
  0x20 = CHECKPOINT marker

On crash recovery: replay all records from last CHECKPOINT.
On normal close: write CHECKPOINT + truncate.
"""

import os
import struct
import json
import zlib

MAGIC = 0x4D494E49  # "MINI"
RECORD_HEADER_FMT = '!IIiBI'  # magic, crc32, txn_id, type, data_len
RECORD_HEADER_SIZE = struct.calcsize(RECORD_HEADER_FMT)

# Record types
R_BEGIN = 0xB0
R_COMMIT = 0xB1
R_ROLLBACK = 0xB2
R_INSERT = 0x10
R_DELETE = 0x11
R_UPDATE = 0x12
R_CHECKPOINT = 0x20
R_TABLE_SCHEMA = 0x30  # CREATE TABLE: table_name, schema JSON

RECORD_NAMES = {
    0xB0: 'BEGIN',
    0xB1: 'COMMIT',
    0xB2: 'ROLLBACK',
    0x10: 'INSERT',
    0x11: 'DELETE',
    0x12: 'UPDATE',
    0x20: 'CHECKPOINT',
    0x30: 'TABLE_SCHEMA',
}


class WALRecord:
    __slots__ = ('txn_id', 'type', 'data')

    def __init__(self, txn_id, typ, data=b''):
        self.txn_id = txn_id
        self.type = typ
        self.data = data

    def __repr__(self):
        return "WAL[txn=%d, type=0x%02x(%s), data=%d bytes]" % (
            self.txn_id, self.type, RECORD_NAMES.get(self.type, '?'), len(self.data))

    def encode(self):
        header = struct.pack(RECORD_HEADER_FMT, MAGIC, 0, self.txn_id, self.type, len(self.data))
        crc = zlib.crc32(header[8:] + self.data) & 0xFFFFFFFF
        header = struct.pack(RECORD_HEADER_FMT, MAGIC, crc, self.txn_id, self.type, len(self.data))
        return header + self.data

    @staticmethod
    def decode(raw):
        if len(raw) < RECORD_HEADER_SIZE:
            return None, 0
        magic, crc, txn_id, typ, data_len = struct.unpack_from(RECORD_HEADER_FMT, raw, 0)
        if magic != MAGIC:
            return None, 0
        total_size = RECORD_HEADER_SIZE + data_len
        if len(raw) < total_size:
            return None, 0
        data = raw[RECORD_HEADER_SIZE:total_size]
        computed_crc = zlib.crc32(raw[8:total_size]) & 0xFFFFFFFF
        if computed_crc != crc:
            return None, total_size  # Corrupted, skip this record
        rec = WALRecord(txn_id, typ, data)
        return rec, total_size


class WAL:
    """Write-Ahead Log manager."""

    def __init__(self, path):
        self.path = path
        self._file = None
        self._size = 0
        self._open()

    def _open(self):
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        try:
            self._file = open(self.path, 'rb+')
        except FileNotFoundError:
            self._file = open(self.path, 'wb+')
        self._file.seek(0, 2)
        self._size = self._file.tell()

    def append(self, record):
        raw = record.encode()
        self._file.seek(0, 2)
        self._file.write(raw)
        self._file.flush()
        os.fsync(self._file.fileno())
        self._size += len(raw)

    def begin(self, txn_id):
        self.append(WALRecord(txn_id, R_BEGIN))

    def commit(self, txn_id):
        self.append(WALRecord(txn_id, R_COMMIT))

    def rollback(self, txn_id):
        self.append(WALRecord(txn_id, R_ROLLBACK))

    def log_insert(self, txn_id, table_name, key, value):
        data = json.dumps([table_name, key, value], ensure_ascii=False).encode('utf-8')
        self.append(WALRecord(txn_id, R_INSERT, data))

    def log_delete(self, txn_id, table_name, key):
        data = json.dumps([table_name, key], ensure_ascii=False).encode('utf-8')
        self.append(WALRecord(txn_id, R_DELETE, data))

    def log_update(self, txn_id, table_name, key, new_value):
        data = json.dumps([table_name, key, new_value], ensure_ascii=False).encode('utf-8')
        self.append(WALRecord(txn_id, R_UPDATE, data))

    def log_table_schema(self, txn_id, table_name, columns):
        data = json.dumps([table_name, columns], ensure_ascii=False).encode('utf-8')
        self.append(WALRecord(txn_id, R_TABLE_SCHEMA, data))

    def log_checkpoint(self):
        self.append(WALRecord(-1, R_CHECKPOINT))
        self._file.seek(0, 2)
        self._size = self._file.tell()

    def replay(self):
        """Replay all WAL records and return (committed_actions, uncommitted_actions, table_schemas)."""
        self._file.seek(0)
        raw = self._file.read()
        records = []
        off = 0
        while off < len(raw):
            rec, consumed = WALRecord.decode(raw[off:])
            if rec is not None:
                records.append(rec)
                off += consumed
            else:
                off += 1  # Skip corrupted byte

        return self._process_records(records)

    def _process_records(self, records):
        """Process records, respecting BEGIN/COMMIT/ROLLBACK boundaries."""
        active_txns = {}  # txn_id -> [records]
        committed = []  # (txn_id, records)
        table_schemas = {}  # table_name -> columns
        last_checkpoint = -1

        for rec in records:
            if rec.type == R_CHECKPOINT:
                last_checkpoint = max(last_checkpoint, rec.txn_id)
                # Clear committed list before checkpoint (already persisted)
                committed = []
                active_txns.clear()
            elif rec.type == R_BEGIN:
                if rec.txn_id not in active_txns:
                    active_txns[rec.txn_id] = []
            elif rec.type == R_COMMIT:
                if rec.txn_id in active_txns:
                    txn_records = active_txns.pop(rec.txn_id)
                    committed.append((rec.txn_id, txn_records))
            elif rec.type == R_ROLLBACK:
                active_txns.pop(rec.txn_id, None)
            elif rec.type == R_TABLE_SCHEMA:
                txn_records = active_txns.get(rec.txn_id)
                if txn_records is not None:
                    txn_records.append(rec)
                # Even if no active txn, apply schema
                name, cols = json.loads(rec.data.decode('utf-8'))
                table_schemas[name] = cols
            else:
                if active_txns:
                    for txn_recs in active_txns.values():
                        txn_recs.append(rec)
                        break

        # Apply DDL/DML from committed
        actions = []
        for txn_id, txn_records in committed:
            for rec in txn_records:
                if rec.type == R_TABLE_SCHEMA:
                    name, cols = json.loads(rec.data.decode('utf-8'))
                    table_schemas[name] = cols
                    actions.append(('table_schema', name, cols))
                elif rec.type == R_INSERT:
                    name, key, val = json.loads(rec.data.decode('utf-8'))
                    actions.append(('insert', name, key, val))
                elif rec.type == R_DELETE:
                    name, key = json.loads(rec.data.decode('utf-8'))
                    actions.append(('delete', name, key))
                elif rec.type == R_UPDATE:
                    name, key, val = json.loads(rec.data.decode('utf-8'))
                    actions.append(('update', name, key, val))

        return committed, active_txns, table_schemas, actions

    def truncate(self):
        """Truncate WAL to 0 bytes after a clean checkpoint."""
        self.close()
        self._file = open(self.path, 'wb')
        self._file.close()
        self._size = 0
        self._file = open(self.path, 'rb+')

    def close(self):
        if self._file:
            self._file.close()
            self._file = None

    def __del__(self):
        self.close()
