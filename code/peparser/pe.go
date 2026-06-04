package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"strings"
	"time"
)

// ==================== 数据结构定义 ====================

// DOS Header
type ImageDosHeader struct {
	Magic           [2]byte // "MZ"
	BytesOnLastPage [2]byte
	PagesInFile     [2]byte
	Relocations     [2]byte
	SizeOfHeader    [2]byte
	MinExtra        [2]byte
	MaxExtra        [2]byte
	Ss              [2]byte
	Sp              [2]byte
	Checksum        [2]byte
	Ip              [2]byte
	Cs              [2]byte
	RelocTableAddr  [2]byte
	OverlayNum      [2]byte
	Reserved        [8]byte
	OEMId           [2]byte
	OEMInfo         [2]byte
	Reserved2       [20]byte
	NewExeAddr      [4]byte // e_lfanew - offset to PE header
}

// COFF File Header
type ImageFileHeader struct {
	Machine              uint16
	NumberOfSections     uint16
	TimeDateStamp        uint32
	PointerToSymbolTable uint32
	NumberOfSymbols      uint32
	SizeOfOptionalHeader uint16
	Characteristics      uint16
}

// Optional Header PE32 (32-bit)
type ImageOptionalHeader32 struct {
	Magic                       uint16 // 0x10b
	MajorLinkerVersion          uint8
	MinorLinkerVersion          uint8
	SizeOfCode                  uint32
	SizeOfInitializedData       uint32
	SizeOfUninitializedData     uint32
	AddressOfEntryPoint         uint32
	BaseOfCode                  uint32
	BaseOfData                  uint32
	ImageBase                   uint32
	SectionAlignment            uint32
	FileAlignment               uint32
	MajorOperatingSystemVersion uint16
	MinorOperatingSystemVersion uint16
	MajorImageVersion           uint16
	MinorImageVersion           uint16
	MajorSubsystemVersion       uint16
	MinorSubsystemVersion       uint16
	Win32VersionValue           uint32
	SizeOfImage                 uint32
	SizeOfHeaders               uint32
	CheckSum                    uint32
	Subsystem                   uint16
	DllCharacteristics          uint16
	SizeOfStackReserve          uint32
	SizeOfStackCommit           uint32
	SizeOfHeapReserve           uint32
	SizeOfHeapCommit            uint32
	LoaderFlags                 uint32
	NumberOfRvaAndSizes         uint32
	DataDirectory               [16]ImageDataDirectory
}

// Optional Header PE32+ (64-bit)
type ImageOptionalHeader64 struct {
	Magic                       uint16 // 0x20b
	MajorLinkerVersion          uint8
	MinorLinkerVersion          uint8
	SizeOfCode                  uint32
	SizeOfInitializedData       uint32
	SizeOfUninitializedData     uint32
	AddressOfEntryPoint         uint32
	BaseOfCode                  uint32
	ImageBase                   uint64
	SectionAlignment            uint32
	FileAlignment               uint32
	MajorOperatingSystemVersion uint16
	MinorOperatingSystemVersion uint16
	MajorImageVersion           uint16
	MinorImageVersion           uint16
	MajorSubsystemVersion       uint16
	MinorSubsystemVersion       uint16
	Win32VersionValue           uint32
	SizeOfImage                 uint32
	SizeOfHeaders               uint32
	CheckSum                    uint32
	Subsystem                   uint16
	DllCharacteristics          uint16
	SizeOfStackReserve          uint64
	SizeOfStackCommit           uint64
	SizeOfHeapReserve           uint64
	SizeOfHeapCommit            uint64
	LoaderFlags                 uint32
	NumberOfRvaAndSizes         uint32
	DataDirectory               [16]ImageDataDirectory
}

// Section Header
type ImageSectionHeader struct {
	Name                 [8]byte
	VirtualSize          uint32
	VirtualAddress       uint32
	SizeOfRawData        uint32
	PointerToRawData     uint32
	PointerToRelocations uint32
	PointerToLinenumbers uint32
	NumberOfRelocations  uint16
	NumberOfLinenumbers  uint16
	Characteristics      uint32
}

// 数据目录项
type ImageDataDirectory struct {
	VirtualAddress uint32
	Size           uint32
}

// 导入描述符
type ImageImportDescriptor struct {
	OriginalFirstThunk uint32
	TimeDateStamp      uint32
	ForwarderChain     uint32
	Name               uint32 // RVA to DLL name
	FirstThunk         uint32
}

// 导出目录
type ImageExportDirectory struct {
	Characteristics       uint32
	TimeDateStamp         uint32
	MajorVersion          uint16
	MinorVersion          uint16
	Name                  uint32
	Base                  uint32
	NumberOfFunctions     uint32
	NumberOfNames         uint32
	AddressOfFunctions    uint32
	AddressOfNames        uint32
	AddressOfNameOrdinals uint32
}

// ==================== 辅助类型 ====================

// ImportInfo 导入信息
type ImportInfo struct {
	DLLName   string
	Functions []string
}

// ExportInfo 导出信息
type ExportInfo struct {
	Name    string
	Ordinal uint32
	Address uint32
}

// ==================== PEFile ====================

// PEFile 表示解析后的 PE 文件
type PEFile struct {
	DosHeader      ImageDosHeader
	PEHeader       ImageFileHeader
	OptionalHeader interface{} // *ImageOptionalHeader32 or *ImageOptionalHeader64
	IsPE32Plus     bool
	Sections       []ImageSectionHeader
	Imports        []ImportInfo
	Exports        []ExportInfo
	FilePath       string

	data []byte // 文件内容
}

// GetDataDirectory 获取数据目录项
func (pe *PEFile) GetDataDirectory() [16]ImageDataDirectory {
	switch h := pe.OptionalHeader.(type) {
	case *ImageOptionalHeader32:
		return h.DataDirectory
	case *ImageOptionalHeader64:
		return h.DataDirectory
	}
	return [16]ImageDataDirectory{}
}

// GetImageBase 获取 ImageBase
func (pe *PEFile) GetImageBase() uint64 {
	switch h := pe.OptionalHeader.(type) {
	case *ImageOptionalHeader32:
		return uint64(h.ImageBase)
	case *ImageOptionalHeader64:
		return h.ImageBase
	}
	return 0
}

// GetAddressOfEntryPoint 获取入口点
func (pe *PEFile) GetAddressOfEntryPoint() uint32 {
	switch h := pe.OptionalHeader.(type) {
	case *ImageOptionalHeader32:
		return h.AddressOfEntryPoint
	case *ImageOptionalHeader64:
		return h.AddressOfEntryPoint
	}
	return 0
}

// GetSizeOfImage 获取镜像大小
func (pe *PEFile) GetSizeOfImage() uint32 {
	switch h := pe.OptionalHeader.(type) {
	case *ImageOptionalHeader32:
		return h.SizeOfImage
	case *ImageOptionalHeader64:
		return h.SizeOfImage
	}
	return 0
}

// GetSectionAlignment 获取节对齐
func (pe *PEFile) GetSectionAlignment() uint32 {
	switch h := pe.OptionalHeader.(type) {
	case *ImageOptionalHeader32:
		return h.SectionAlignment
	case *ImageOptionalHeader64:
		return h.SectionAlignment
	}
	return 0
}

// GetFileAlignment 获取文件对齐
func (pe *PEFile) GetFileAlignment() uint32 {
	switch h := pe.OptionalHeader.(type) {
	case *ImageOptionalHeader32:
		return h.FileAlignment
	case *ImageOptionalHeader64:
		return h.FileAlignment
	}
	return 0
}

// GetSubsystem 获取子系统
func (pe *PEFile) GetSubsystem() uint16 {
	switch h := pe.OptionalHeader.(type) {
	case *ImageOptionalHeader32:
		return h.Subsystem
	case *ImageOptionalHeader64:
		return h.Subsystem
	}
	return 0
}

// ==================== 解析逻辑 ====================

// ParseFile 从文件路径解析 PE
func ParseFile(path string) (*PEFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	pe := &PEFile{FilePath: path, data: data}

	// 1. 验证 DOS Header
	reader := bytes.NewReader(data)
	var dos ImageDosHeader
	if err := binary.Read(reader, binary.LittleEndian, &dos); err != nil {
		return nil, fmt.Errorf("读取 DOS 头失败: %v", err)
	}
	if dos.Magic[0] != 'M' || dos.Magic[1] != 'Z' {
		return nil, fmt.Errorf("不是有效的 PE 文件: 缺少 MZ 签名")
	}
	pe.DosHeader = dos

	// 2. 跳转到 PE Header
	peOffset := int64(binary.LittleEndian.Uint32(dos.NewExeAddr[:]))
	if peOffset <= 0 || int(peOffset) >= len(data) {
		return nil, fmt.Errorf("无效的 PE 偏移: 0x%X", peOffset)
	}
	reader.Seek(peOffset, io.SeekStart)

	// 3. 验证 PE Signature
	var sig uint32
	if err := binary.Read(reader, binary.LittleEndian, &sig); err != nil {
		return nil, fmt.Errorf("读取 PE 签名失败: %v", err)
	}
	if sig != 0x00004550 { // "PE\0\0"
		return nil, fmt.Errorf("不是有效的 PE 文件: 缺少 PE 签名 (got 0x%08X)", sig)
	}

	// 4. 读取 COFF File Header
	if err := binary.Read(reader, binary.LittleEndian, &pe.PEHeader); err != nil {
		return nil, fmt.Errorf("读取 COFF 文件头失败: %v", err)
	}

	// 验证 NumberOfSections 合理性
	if pe.PEHeader.NumberOfSections > 100 {
		return nil, fmt.Errorf("节数量异常: %d", pe.PEHeader.NumberOfSections)
	}

	// 5. 读取 Optional Header
	magicBytes := make([]byte, 2)
	if _, err := reader.Read(magicBytes); err != nil {
		return nil, fmt.Errorf("读取 Optional Header magic 失败: %v", err)
	}
	reader.Seek(-2, io.SeekCurrent)

	magic := binary.LittleEndian.Uint16(magicBytes)

	switch magic {
	case 0x010b: // PE32
		pe.IsPE32Plus = false
		var opt32 ImageOptionalHeader32
		if err := binary.Read(reader, binary.LittleEndian, &opt32); err != nil {
			return nil, fmt.Errorf("读取 Optional Header (PE32) 失败: %v", err)
		}
		pe.OptionalHeader = &opt32

	case 0x020b: // PE32+
		pe.IsPE32Plus = true
		var opt64 ImageOptionalHeader64
		if err := binary.Read(reader, binary.LittleEndian, &opt64); err != nil {
			return nil, fmt.Errorf("读取 Optional Header (PE32+) 失败: %v", err)
		}
		pe.OptionalHeader = &opt64

	default:
		return nil, fmt.Errorf("未知的 Optional Header magic: 0x%04X", magic)
	}

	// 6. 读取 Section Table
	pe.Sections = make([]ImageSectionHeader, pe.PEHeader.NumberOfSections)
	for i := uint16(0); i < pe.PEHeader.NumberOfSections; i++ {
		if err := binary.Read(reader, binary.LittleEndian, &pe.Sections[i]); err != nil {
			return nil, fmt.Errorf("读取第 %d 个节头失败: %v", i, err)
		}
	}

	// 7. 解析导入表
	if err := pe.parseImports(); err != nil {
		// 导入表解析失败不阻止整体解析
		// 只记录错误
		_ = err
	}

	// 8. 解析导出表
	if err := pe.parseExports(); err != nil {
		_ = err
	}

	return pe, nil
}

// RVA 转文件偏移
func (pe *PEFile) RVAToOffset(rva uint32) uint32 {
	for _, section := range pe.Sections {
		if rva >= section.VirtualAddress && rva < section.VirtualAddress+section.VirtualSize {
			return rva - section.VirtualAddress + section.PointerToRawData
		}
	}
	return rva
}

// 在数据范围内检查偏移
func (pe *PEFile) safeOffset(offset uint32) bool {
	return int(offset) >= 0 && int(offset) < len(pe.data)
}

// 在数据范围内检查范围
func (pe *PEFile) safeRange(offset uint32, size uint32) bool {
	return pe.safeOffset(offset) && int(offset+size) <= len(pe.data) && size > 0
}

// parseImports 解析导入表
func (pe *PEFile) parseImports() error {
	dirs := pe.GetDataDirectory()
	importDir := dirs[1] // IMAGE_DIRECTORY_ENTRY_IMPORT
	if importDir.VirtualAddress == 0 {
		return nil
	}

	offset := pe.RVAToOffset(importDir.VirtualAddress)
	if !pe.safeOffset(offset) {
		return fmt.Errorf("导入表偏移超出文件范围: 0x%X", offset)
	}

	reader := bytes.NewReader(pe.data[offset:])

	for {
		var desc ImageImportDescriptor
		if err := binary.Read(reader, binary.LittleEndian, &desc); err != nil {
			break
		}
		if desc.Name == 0 {
			break
		}

		// 读取 DLL 名称
		nameOffset := pe.RVAToOffset(desc.Name)
		if !pe.safeOffset(nameOffset) {
			continue
		}
		dllName := readCString(pe.data[nameOffset:])
		if dllName == "" {
			continue
		}

		// 读取导入函数/序号
		thunkOffset := pe.RVAToOffset(desc.OriginalFirstThunk)
		if thunkOffset == 0 {
			thunkOffset = pe.RVAToOffset(desc.FirstThunk)
		}
		if thunkOffset == 0 || !pe.safeOffset(thunkOffset) {
			continue
		}

		var functions []string
		thunkReader := bytes.NewReader(pe.data[thunkOffset:])

		for {
			var thunkValue uint64
			if pe.IsPE32Plus {
				if err := binary.Read(thunkReader, binary.LittleEndian, &thunkValue); err != nil {
					break
				}
			} else {
				var val32 uint32
				if err := binary.Read(thunkReader, binary.LittleEndian, &val32); err != nil {
					break
				}
				thunkValue = uint64(val32)
			}
			if thunkValue == 0 {
				break
			}

			// 判断是否按序号导入
			// PE32+ 用高 bit 判断，PE32 用 IMAGE_SNAP_BY_ORDINAL32
			if pe.IsPE32Plus && (thunkValue&0x8000000000000000 != 0) {
				ordinal := uint16(thunkValue & 0xFFFF)
				functions = append(functions, fmt.Sprintf("ordinal(%d)", ordinal))
			} else if !pe.IsPE32Plus && (thunkValue&0x80000000 != 0) {
				ordinal := uint16(thunkValue & 0xFFFF)
				functions = append(functions, fmt.Sprintf("ordinal(%d)", ordinal))
			} else {
				// 按名称导入：IMAGE_IMPORT_BY_NAME 结构
				funcOffset := pe.RVAToOffset(uint32(thunkValue))
				if !pe.safeRange(funcOffset, 2) {
					functions = append(functions, fmt.Sprintf("???(rva=0x%X)", thunkValue))
					continue
				}
				hint := binary.LittleEndian.Uint16(pe.data[funcOffset:])
				funcName := readCString(pe.data[funcOffset+2:])
				if funcName == "" {
					functions = append(functions, fmt.Sprintf("hint(0x%04X)", hint))
				} else {
					functions = append(functions, funcName)
				}
			}
		}

		if len(functions) > 0 {
			pe.Imports = append(pe.Imports, ImportInfo{
				DLLName:   dllName,
				Functions: functions,
			})
		}
	}

	return nil
}

// parseExports 解析导出表
func (pe *PEFile) parseExports() error {
	dirs := pe.GetDataDirectory()
	exportDir := dirs[0] // IMAGE_DIRECTORY_ENTRY_EXPORT
	if exportDir.VirtualAddress == 0 {
		return nil
	}

	offset := pe.RVAToOffset(exportDir.VirtualAddress)
	if !pe.safeOffset(offset) {
		return fmt.Errorf("导出表偏移超出文件范围: 0x%X", offset)
	}

	reader := bytes.NewReader(pe.data[offset:])

	var export ImageExportDirectory
	if err := binary.Read(reader, binary.LittleEndian, &export); err != nil {
		return fmt.Errorf("读取导出目录失败: %v", err)
	}

	// 验证导出表数据
	if export.NumberOfNames == 0 || export.NumberOfFunctions == 0 {
		return nil
	}

	// 读取函数地址表
	funcAddrOffset := pe.RVAToOffset(export.AddressOfFunctions)
	if !pe.safeRange(funcAddrOffset, export.NumberOfFunctions*4) {
		return fmt.Errorf("导出函数地址表超出文件范围")
	}

	// 读取名称表
	nameOffsetAddr := pe.RVAToOffset(export.AddressOfNames)
	if !pe.safeRange(nameOffsetAddr, export.NumberOfNames*4) {
		return fmt.Errorf("导出名称表超出文件范围")
	}

	// 读取序号表
	ordinalOffset := pe.RVAToOffset(export.AddressOfNameOrdinals)
	if !pe.safeRange(ordinalOffset, export.NumberOfNames*2) {
		return fmt.Errorf("导出序号表超出文件范围")
	}

	for i := uint32(0); i < export.NumberOfNames; i++ {
		nameRVA := binary.LittleEndian.Uint32(pe.data[nameOffsetAddr+i*4:])
		funcNameOff := pe.RVAToOffset(nameRVA)
		if !pe.safeOffset(funcNameOff) {
			continue
		}
		funcName := readCString(pe.data[funcNameOff:])
		if funcName == "" {
			continue
		}

		ordinalIdx := binary.LittleEndian.Uint16(pe.data[ordinalOffset+i*2:])
		if uint32(ordinalIdx) >= export.NumberOfFunctions {
			continue
		}
		funcAddr := binary.LittleEndian.Uint32(pe.data[funcAddrOffset+uint32(ordinalIdx)*4:])

		pe.Exports = append(pe.Exports, ExportInfo{
			Name:    funcName,
			Ordinal: export.Base + uint32(ordinalIdx),
			Address: funcAddr,
		})
	}

	return nil
}

// ==================== 辅助函数 ====================

// readCString 读取 C 风格字符串（以 \0 结尾）
func readCString(data []byte) string {
	var end int
	for end < len(data) && data[end] != 0 {
		end++
	}
	return string(data[:end])
}

// sectionName 将节名称转为字符串
func sectionName(name [8]byte) string {
	var b []byte
	for _, c := range name {
		if c == 0 {
			break
		}
		b = append(b, c)
	}
	return string(b)
}

// ==================== 报告输出 ====================

// PrintReport 输出解析报告
func (pe *PEFile) PrintReport() {
	sep := strings.Repeat("=", 60)
	fmt.Println(sep)
	fmt.Println("📦 PE 文件分析报告")
	fmt.Println(sep)
	fmt.Printf("文件: %s\n", pe.FilePath)
	fmt.Printf("大小: %d bytes\n", len(pe.data))

	fmt.Println("\n--- DOS Header ---")
	fmt.Printf("Magic: %c%c\n", pe.DosHeader.Magic[0], pe.DosHeader.Magic[1])
	fmt.Printf("PE 偏移: 0x%X\n", binary.LittleEndian.Uint32(pe.DosHeader.NewExeAddr[:]))

	fmt.Println("\n--- COFF File Header ---")
	fmt.Printf("Machine: 0x%04X (%s)\n", pe.PEHeader.Machine, machineName(pe.PEHeader.Machine))
	fmt.Printf("Sections: %d\n", pe.PEHeader.NumberOfSections)
	ts := time.Unix(int64(pe.PEHeader.TimeDateStamp), 0)
	fmt.Printf("时间戳: %s\n", ts.Format("2006-01-02 15:04:05"))
	fmt.Printf("Characteristics: 0x%04X\n", pe.PEHeader.Characteristics)

	fmt.Println("\n--- Optional Header ---")
	if pe.IsPE32Plus {
		fmt.Println("格式: PE32+ (64-bit)")
	} else {
		fmt.Println("格式: PE32 (32-bit)")
	}
	fmt.Printf("入口点: 0x%X\n", pe.GetAddressOfEntryPoint())
	fmt.Printf("Image Base: 0x%X\n", pe.GetImageBase())
	fmt.Printf("Section Alignment: 0x%X\n", pe.GetSectionAlignment())
	fmt.Printf("File Alignment: 0x%X\n", pe.GetFileAlignment())
	imageSize := pe.GetSizeOfImage()
	fmt.Printf("镜像大小: 0x%X (%d KB)\n", imageSize, imageSize/1024)
	fmt.Printf("子系统: %s\n", subsystemName(pe.GetSubsystem()))

	fmt.Println("\n--- Sections ---")
	fmt.Printf("%-10s %-12s %-12s %-12s %-12s %s\n",
		"Name", "VirtualSz", "VirtualAddr", "RawSz", "RawAddr", "Characteristics")
	for _, s := range pe.Sections {
		charStr := sectionChar(s.Characteristics)
		fmt.Printf("%-10s %-12d 0x%08X %-12d 0x%08X %s\n",
			sectionName(s.Name),
			s.VirtualSize,
			s.VirtualAddress,
			s.SizeOfRawData,
			s.PointerToRawData,
			charStr)
	}

	if len(pe.Imports) > 0 {
		fmt.Println("\n--- Import Table ---")
		for _, imp := range pe.Imports {
			fmt.Printf("📥 %s\n", imp.DLLName)
			maxShow := 10
			if len(imp.Functions) > maxShow {
				for _, fn := range imp.Functions[:maxShow] {
					fmt.Printf("  ├─ %s\n", fn)
				}
				fmt.Printf("  └─ ... (%d more)\n", len(imp.Functions)-maxShow)
			} else {
				for _, fn := range imp.Functions {
					fmt.Printf("  ├─ %s\n", fn)
				}
			}
		}
	} else {
		fmt.Println("\n--- Import Table ---")
		fmt.Println("  (无导入表)")
	}

	if len(pe.Exports) > 0 {
		fmt.Println("\n--- Export Table ---")
		fmt.Printf("导出 %d 个函数\n", len(pe.Exports))
		maxShow := 10
		if len(pe.Exports) > maxShow {
			for _, exp := range pe.Exports[:maxShow] {
				fmt.Printf("📤 [%d] %s @ 0x%X\n", exp.Ordinal, exp.Name, exp.Address)
			}
			fmt.Printf("  ... (%d more)\n", len(pe.Exports)-maxShow)
		} else {
			for _, exp := range pe.Exports {
				fmt.Printf("📤 [%d] %s @ 0x%X\n", exp.Ordinal, exp.Name, exp.Address)
			}
		}
	} else {
		fmt.Println("\n--- Export Table ---")
		fmt.Println("  (无导出表)")
	}

	fmt.Println("\n" + sep)
}

// machineName 返回机器类型名称
func machineName(machine uint16) string {
	names := map[uint16]string{
		0x014c: "I386",
		0x8664: "AMD64",
		0x0200: "IA64",
		0x01c4: "ARM64",
		0x01c0: "ARM",
		0x01c2: "ARM Thumb",
		0x0EBC: "EFI Byte Code",
		0x01c6: "ARM64EC",
		0x01d2: "ARM64X",
		0x00e2: "I386 with HTC (MIPS)",
		0x0166: "MIPS16",
		0x0201: "Alpha_AXP",
		0x0284: "SH3",
		0x0366: "PowerPC",
		0x01F0: "PowerPC LE",
		0x0204: "SH4",
		0x0266: "M68K",
		0x0303: "Itanium",
		0x5032: "x86_64 (Chpe X86)",
		0x0000: "UNKNOWN",
	}
	if name, ok := names[machine]; ok {
		return name
	}
	return "Unknown"
}

// subsystemName 返回子系统名称
func subsystemName(s uint16) string {
	switch s {
	case 0:
		return "UNKNOWN"
	case 1:
		return "NATIVE"
	case 2:
		return "WINDOWS_GUI"
	case 3:
		return "WINDOWS_CUI"
	case 5:
		return "OS2_CUI"
	case 7:
		return "POSIX_CUI"
	case 8:
		return "Native_Windows"
	case 9:
		return "Windows_CE_GUI"
	case 10:
		return "EFI_APPLICATION"
	case 11:
		return "EFI_BOOT_SERVICE_DRIVER"
	case 12:
		return "EFI_RUNTIME_DRIVER"
	case 13:
		return "EFI_ROM"
	case 14:
		return "XBOX"
	case 15:
		return "Windows_Boot_Application"
	case 16:
		return "XBOX_CODE_CATALOG"
	default:
		return fmt.Sprintf("Unknown(0x%X)", s)
	}
}

// sectionChar 返回节特性的字符串表示
func sectionChar(ch uint32) string {
	chars := []struct {
		flag uint32
		name string
	}{
		{0x00000020, "CODE"},
		{0x00000040, "INIT_DATA"},
		{0x00000080, "UNINIT_DATA"},
		{0x02000000, "DISCARDABLE"},
		{0x04000000, "NOT_CACHED"},
		{0x08000000, "NOT_PAGED"},
		{0x10000000, "SHARED"},
		{0x20000000, "EXECUTE"},
		{0x40000000, "READ"},
		{0x80000000, "WRITE"},
	}
	var result []string
	for _, c := range chars {
		if ch&c.flag != 0 {
			result = append(result, c.name)
		}
	}
	if len(result) == 0 {
		return "[NONE]"
	}
	return "[" + strings.Join(result, "|") + "]"
}
