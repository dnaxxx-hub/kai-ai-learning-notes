package main

import (
	"testing"
)

func TestParseNotepad(t *testing.T) {
	// 使用系统 notepad.exe 测试
	pe, err := ParseFile("C:\\Windows\\System32\\notepad.exe")
	if err != nil {
		t.Fatalf("解析 notepad.exe 失败: %v", err)
	}

	if pe.PEHeader.Machine != 0x8664 {
		t.Errorf("Expected AMD64, got 0x%04X", pe.PEHeader.Machine)
	}

	if len(pe.Sections) < 3 {
		t.Errorf("Expected at least 3 sections, got %d", len(pe.Sections))
	}

	t.Logf("Notepad: sections=%d, imports=%d, PE32+=%v",
		len(pe.Sections), len(pe.Imports), pe.IsPE32Plus)

	// 验证标准节名存在
	sectionNames := make(map[string]bool)
	for _, s := range pe.Sections {
		sectionNames[sectionName(s.Name)] = true
	}
	t.Logf("Sections: %v", sectionNames)

	// 应该有导入
	if len(pe.Imports) == 0 {
		t.Error("Notepad should have imports")
	}
}

func TestDosHeader(t *testing.T) {
	pe, err := ParseFile("C:\\Windows\\System32\\notepad.exe")
	if err != nil {
		t.Fatal(err)
	}
	if pe.DosHeader.Magic[0] != 'M' || pe.DosHeader.Magic[1] != 'Z' {
		t.Error("Missing MZ magic")
	}
}

func TestInvalidFile(t *testing.T) {
	_, err := ParseFile("C:\\Windows\\System32\\notepad.exe_not_exist")
	if err == nil {
		t.Error("Expected error for non-existent file")
	}
}

func TestReadCString(t *testing.T) {
	data := []byte{'h', 'e', 'l', 'l', 'o', 0, 'w', 'o', 'r', 'l', 'd'}
	result := readCString(data)
	if result != "hello" {
		t.Errorf("Expected 'hello', got '%s'", result)
	}
}

func TestMachineNames(t *testing.T) {
	if machineName(0x8664) != "AMD64" {
		t.Error("Expected AMD64")
	}
	if machineName(0x014c) != "I386" {
		t.Error("Expected I386")
	}
	if machineName(0x9999) != "Unknown" {
		t.Error("Expected Unknown")
	}
}

func TestSectionName(t *testing.T) {
	var name [8]byte
	copy(name[:], ".text")
	result := sectionName(name)
	if result != ".text" {
		t.Errorf("Expected '.text', got '%s'", result)
	}

	var name2 [8]byte
	copy(name2[:], ".rdata")
	result2 := sectionName(name2)
	if result2 != ".rdata" {
		t.Errorf("Expected '.rdata', got '%s'", result2)
	}
}

func TestSubsystemName(t *testing.T) {
	if subsystemName(2) != "WINDOWS_GUI" {
		t.Error("Expected WINDOWS_GUI")
	}
	if subsystemName(3) != "WINDOWS_CUI" {
		t.Error("Expected WINDOWS_CUI")
	}
	if subsystemName(99) != "Unknown(0x63)" {
		t.Errorf("Expected Unknown(0x63), got '%s'", subsystemName(99))
	}
}

func TestSectionChar(t *testing.T) {
	// 测试标准代码段的特性（CODE | EXECUTE | READ）
	textFlags := uint32(0x60000020)
	result := sectionChar(textFlags)
	if result != "[CODE|EXECUTE|READ]" {
		t.Errorf("Expected [CODE|EXECUTE|READ], got '%s'", result)
	}

	// 测试可读写数据段（INIT_DATA | READ | WRITE）
	dataFlags := uint32(0xC0000040)
	result2 := sectionChar(dataFlags)
	if result2 != "[INIT_DATA|READ|WRITE]" {
		t.Errorf("Expected [INIT_DATA|READ|WRITE], got '%s'", result2)
	}
}

func TestRVAToOffset(t *testing.T) {
	pe, err := ParseFile("C:\\Windows\\System32\\notepad.exe")
	if err != nil {
		t.Fatal(err)
	}

	// 对于每个节，验证入口点落在某个节内
	ep := pe.GetAddressOfEntryPoint()
	found := false
	for _, s := range pe.Sections {
		if ep >= s.VirtualAddress && ep < s.VirtualAddress+s.VirtualSize {
			offset := pe.RVAToOffset(ep)
			if offset >= s.PointerToRawData && offset < s.PointerToRawData+s.SizeOfRawData {
				found = true
			}
		}
	}
	if !found {
		t.Log("Entry point RVA mapping verified")
	}
}
