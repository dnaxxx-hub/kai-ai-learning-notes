"""股票看板 — 纯 Win32 API"""

import win32gui
import win32con
import win32api
import win32ui
# pywin32 provides win32gui/win32con/win32api as top-level modules
from pywin.mfc import window
import threading
import time
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from stock_client import get_portfolio_data, format_stock_data

# 窗口常量
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 400
REFRESH_SECONDS = 5

class StockWidgetWindow:
    """股票看板窗口"""
    
    def __init__(self):
        self.hwnd = None
        self.hdc = None
        self.stock_data = []
        self.last_refresh = 0
        self.running = True
        
        # 颜色定义
        self.COLOR_BG = win32api.RGB(20, 20, 30)
        self.COLOR_TEXT = win32api.RGB(200, 200, 210)
        self.COLOR_GREEN = win32api.RGB(50, 200, 100)
        self.COLOR_RED = win32api.RGB(220, 80, 80)
        self.COLOR_YELLOW = win32api.RGB(220, 200, 50)
        self.COLOR_HEADER = win32api.RGB(100, 120, 180)
        self.COLOR_ACCENT = win32api.RGB(60, 60, 90)
    
    def register_class(self):
        """注册窗口类"""
        wc = win32gui.WNDCLASS()
        wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wc.lpfnWndProc = self.wndproc
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32gui.GetStockObject(win32con.BLACK_BRUSH)
        wc.lpszClassName = "StockWidget"
        self.class_atom = win32gui.RegisterClass(wc)
    
    def create_window(self):
        """创建窗口"""
        self.register_class()
        
        # 计算居中位置
        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        x = (screen_w - WINDOW_WIDTH) // 2
        y = (screen_h - WINDOW_HEIGHT) // 2
        
        self.hwnd = win32gui.CreateWindow(
            "StockWidget",                    # 类名
            "📊 股票看板 — Kai",               # 标题
            win32con.WS_OVERLAPPEDWINDOW | 
            win32con.WS_VISIBLE,              # 样式
            x, y,                             # 位置
            WINDOW_WIDTH, WINDOW_HEIGHT,      # 大小
            0, 0,                             # 父窗口、菜单
            win32api.GetModuleHandle(None),   # 实例
            None
        )
    
    def wndproc(self, hwnd, msg, wparam, lparam):
        """窗口消息处理"""
        if msg == win32con.WM_PAINT:
            self.on_paint()
            return 0
        elif msg == win32con.WM_DESTROY:
            self.running = False
            win32gui.PostQuitMessage(0)
            return 0
        elif msg == win32con.WM_SIZE:
            # 重绘
            win32gui.InvalidateRect(hwnd, None, True)
            return 0
        elif msg == win32con.WM_TIMER:
            self.refresh_data()
            return 0
        
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    
    def on_paint(self):
        """绘制窗口内容"""
        hdc, paintStruct = win32gui.BeginPaint(self.hwnd)
        
        # 创建双缓冲
        rect = win32gui.GetClientRect(self.hwnd)
        hdc_mem = win32gui.CreateCompatibleDC(hdc)
        hbitmap = win32gui.CreateCompatibleBitmap(hdc, rect[2], rect[3])
        win32gui.SelectObject(hdc_mem, hbitmap)
        
        # 清空背景
        brush = win32gui.CreateSolidBrush(self.COLOR_BG)
        win32gui.FillRect(hdc_mem, rect, brush)
        win32gui.DeleteObject(brush)
        
        # 绘制内容
        self.draw_header(hdc_mem, rect)
        self.draw_stocks(hdc_mem, rect)
        self.draw_footer(hdc_mem, rect)
        
        # 复制到窗口
        win32gui.BitBlt(hdc, 0, 0, rect[2], rect[3], hdc_mem, 0, 0, win32con.SRCCOPY)
        
        # 清理
        win32gui.DeleteObject(hbitmap)
        win32gui.DeleteDC(hdc_mem)
        win32gui.EndPaint(self.hwnd, paintStruct)
    
    def draw_header(self, hdc, rect):
        """绘制标题头"""
        font = win32gui.CreateFont(
            -24, 0, 0, 0, win32con.FW_BOLD, 0, 0, 0,
            win32con.DEFAULT_CHARSET,
            0, 0, 0, 0,
            "Segoe UI"
        )
        win32gui.SelectObject(hdc, font)
        win32gui.SetTextColor(hdc, self.COLOR_HEADER)
        win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
        win32gui.TextOut(hdc, 20, 15, "📊 股票看板")
        win32gui.DeleteObject(font)
        
        # 分隔线
        pen = win32gui.CreatePen(win32con.PS_SOLID, 1, self.COLOR_ACCENT)
        win32gui.SelectObject(hdc, pen)
        win32gui.MoveToEx(hdc, 20, 55)
        win32gui.LineTo(hdc, rect[2] - 20, 55)
        win32gui.DeleteObject(pen)
    
    def draw_stocks(self, hdc, rect):
        """绘制股票信息"""
        if not self.stock_data:
            font = win32gui.CreateFont(
                -16, 0, 0, 0, win32con.FW_NORMAL, 0, 0, 0,
                win32con.DEFAULT_CHARSET,
                0, 0, 0, 0,
                "Segoe UI"
            )
            win32gui.SelectObject(hdc, font)
            win32gui.SetTextColor(hdc, self.COLOR_TEXT)
            win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
            win32gui.TextOut(hdc, 20, 80, "正在连接 live-portfolio...")
            win32gui.DeleteObject(font)
            return
        
        y = 75
        
        for stock in self.stock_data:
            # 股票名称 + 价格
            font_name = win32gui.CreateFont(
                -18, 0, 0, 0, win32con.FW_BOLD, 0, 0, 0,
                win32con.DEFAULT_CHARSET,
                0, 0, 0, 0,
                "Segoe UI"
            )
            win32gui.SelectObject(hdc, font_name)
            win32gui.SetTextColor(hdc, self.COLOR_TEXT)
            win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
            
            name_text = f"{stock['name']}  ({stock['code']})"
            win32gui.TextOut(hdc, 20, y, name_text)
            
            # 价格
            price_text = f"¥{stock['price']:.2f}"
            win32gui.TextOut(hdc, rect[2] - 150, y, price_text)
            
            y += 28
            win32gui.DeleteObject(font_name)
            
            # 涨跌
            font_change = win32gui.CreateFont(
                -16, 0, 0, 0, win32con.FW_SEMIBOLD, 0, 0, 0,
                win32con.DEFAULT_CHARSET,
                0, 0, 0, 0,
                "Segoe UI"
            )
            win32gui.SelectObject(hdc, font_change)
            
            pct = stock['change_pct']
            change_color = self.COLOR_GREEN if pct >= 0 else self.COLOR_RED
            change_text = f"{pct:+.2f}%"
            
            win32gui.SetTextColor(hdc, change_color)
            win32gui.TextOut(hdc, 20, y, change_text)
            
            # 指标行
            win32gui.SetTextColor(hdc, self.COLOR_TEXT)
            metrics = (
                f"波动: {stock['volatility']:.1f}%  "
                f"胜率: {stock['win_prob']:.0f}%  "
                f"Kelly: {stock['kelly']:.0f}%"
            )
            win32gui.TextOut(hdc, rect[2] - 300, y, metrics)
            
            y += 25
            win32gui.DeleteObject(font_change)
            
            # 信号
            font_signal = win32gui.CreateFont(
                -14, 0, 0, 0, win32con.FW_LIGHT, 0, 0, 0,
                win32con.DEFAULT_CHARSET,
                0, 0, 0, 0,
                "Segoe UI"
            )
            win32gui.SelectObject(hdc, font_signal)
            
            signal = stock.get('signal', '')
            pos = stock.get('position', '')
            
            signal_color = self.COLOR_GREEN
            if '↓' in signal:
                signal_color = self.COLOR_RED
            elif '→' in signal:
                signal_color = self.COLOR_YELLOW
            
            win32gui.SetTextColor(hdc, signal_color)
            win32gui.TextOut(hdc, 20, y, f"建议: {pos} {signal}")
            
            y += 35
            win32gui.DeleteObject(font_signal)
            
            # 股票之间的分隔
            if y < rect[3] - 60:
                pen = win32gui.CreatePen(win32con.PS_DOT, 1, self.COLOR_ACCENT)
                win32gui.SelectObject(hdc, pen)
                win32gui.MoveToEx(hdc, 20, y)
                win32gui.LineTo(hdc, rect[2] - 20, y)
                win32gui.DeleteObject(pen)
                y += 15
    
    def draw_footer(self, hdc, rect):
        """绘制底部信息"""
        font = win32gui.CreateFont(
            -12, 0, 0, 0, win32con.FW_LIGHT, 1, 0, 0,
            win32con.DEFAULT_CHARSET,
            0, 0, 0, 0,
            "Segoe UI"
        )
        win32gui.SelectObject(hdc, font)
        win32gui.SetTextColor(hdc, self.COLOR_ACCENT)
        win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
        
        from datetime import datetime
        footer = f"Kai · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        text_w, text_h = 0, 0
        win32gui.TextOut(hdc, 20, rect[3] - 30, footer)
        
        win32gui.DeleteObject(font)
    
    def refresh_data(self):
        """定时刷新数据"""
        data = get_portfolio_data()
        self.stock_data = format_stock_data(data)
        win32gui.InvalidateRect(self.hwnd, None, True)
    
    def run(self):
        """主循环"""
        self.create_window()
        
        # 初始加载数据
        self.refresh_data()
        
        # 设置定时器（每5秒刷新）
        win32gui.SetTimer(self.hwnd, 1, REFRESH_SECONDS * 1000, None)
        
        # 消息循环
        while self.running:
            win32gui.PumpWaitingMessages()
            time.sleep(0.05)

def main():
    app = StockWidgetWindow()
    app.run()

if __name__ == "__main__":
    main()
