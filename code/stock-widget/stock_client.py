"""从 live-portfolio 获取股票数据的客户端"""
import httpx
import json

PORTFOLIO_URL = "http://localhost:8080/api/status"

def get_portfolio_data() -> dict:
    """获取实盘数据"""
    try:
        resp = httpx.get(PORTFOLIO_URL, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"stocks": [], "error": str(e)}

def format_stock_data(data: dict) -> list[dict]:
    """将原始数据格式化为显示友好的结构"""
    stocks = data.get("stocks", [])
    result = []
    for s in stocks:
        result.append({
            "name": s.get("name", "N/A"),
            "code": s.get("code", "N/A"),
            "price": s.get("currentPrice", 0),
            "change_pct": s.get("change", 0),
            "volatility": s.get("volatility", 0) * 100,
            "win_prob": s.get("winProb", 0) * 100,
            "kelly": s.get("kellyFrac", 0) * 100,
            "signal": s.get("signal", ""),
            "position": s.get("suggestedPos", ""),
        })
    return result
