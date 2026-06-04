package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("用法: peparser <PE文件路径>")
		fmt.Println("示例:")
		fmt.Println("  peparser.exe \"C:\\Windows\\System32\\notepad.exe\"")
		fmt.Println("  peparser.exe \"C:\\Windows\\System32\\kernel32.dll\"")
		os.Exit(1)
	}

	path := os.Args[1]
	pe, err := ParseFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误: %v\n", err)
		os.Exit(1)
	}

	// 输出报告
	pe.PrintReport()
}
