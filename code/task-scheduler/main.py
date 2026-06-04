import sys
import os


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py server                # Start server")
        print("  python main.py submit <name> [args]  # Submit task")
        print("  python main.py result <task_id>      # Get result")
        print("  python main.py queue-size            # Queue size")
        print("  python main.py recent [status]       # Recent results")
        print("  python main.py workers               # Worker info")
        print("  python main.py schedule <name> <task> <interval>")
        return

    cmd = sys.argv[1]

    if cmd == 'server':
        from server import TaskSchedulerServer
        srv = TaskSchedulerServer()
        srv.start()

    elif cmd == 'submit':
        if len(sys.argv) < 3:
            print("Usage: python main.py submit <name> [args_json]")
            return
        name = sys.argv[2]
        from client import submit
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
        kwargs = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        resp = submit(name, args=args, kwargs=kwargs)
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    elif cmd == 'result':
        if len(sys.argv) < 3:
            print("Usage: python main.py result <task_id>")
            return
        from client import result
        resp = result(sys.argv[2])
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    elif cmd == 'queue-size':
        from client import queue_size
        resp = queue_size()
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    elif cmd == 'recent':
        from client import recent
        status = sys.argv[2] if len(sys.argv) > 2 else None
        resp = recent(status=status)
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    elif cmd == 'workers':
        from client import workers
        resp = workers()
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    elif cmd == 'schedule':
        if len(sys.argv) < 5:
            print("Usage: python main.py schedule <name> <task_name> <interval>")
            return
        from client import schedule
        resp = schedule(sys.argv[2], sys.argv[3], interval=int(sys.argv[4]))
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown command: {cmd}")


if __name__ == '__main__':
    main()
