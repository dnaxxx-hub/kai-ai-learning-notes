# 因子合成与优化

> 从IC/IR到多因子选股评分系统 — 全流程代码实战

---

## 1. IC和IR：因子评价指标

```python
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

def calc_ic(factor_values, forward_returns):
    """计算因子IC（Information Coefficient）
    IC = 因子值与未来收益的秩相关系数
    IC > 0: 因子正向预测收益
    """
    ic = []
    for t in range(len(factor_values)):
        f = factor_values[t]
        r = forward_returns[t]
        mask = ~(np.isnan(f) | np.isnan(r))
        if mask.sum() > 2:
            ic_t, _ = spearmanr(f[mask], r[mask])
            ic.append(ic_t)
    return np.array(ic)

def calc_ir(ic_series):
    """IR = mean(IC) / std(IC)
    IR > 0.5: 好因子，IR > 1.0: 极好
    """
    return np.mean(ic_series) / (np.std(ic_series) + 1e-10)

def factor_rank_ic(factor_df, return_df):
    """多期Rank IC计算"""
    periods = factor_df.index.intersection(return_df.index)
    ic_values = {}
    
    for factor_name in factor_df.columns:
        ics = []
        for t in periods:
            f = factor_df.loc[t, factor_name]
            r = return_df.loc[t, 'ret']
            mask = ~(np.isnan(f) | np.isnan(r))
            if mask.sum() > 5:
                ic_t, _ = spearmanr(f[mask], r[mask])
                ics.append(ic_t)
        ic_values[factor_name] = {
            'IC_mean': np.mean(ics),
            'IC_std': np.std(ics),
            'IR': np.mean(ics) / (np.std(ics) + 1e-10),
            'IC_positive_ratio': np.mean(np.array(ics) > 0)
        }
    
    return pd.DataFrame(ic_values).T

# 示例
np.random.seed(42)
n_stocks = 50
n_periods = 252

# 模拟3个因子
factor_data = {
    'momentum': np.random.randn(n_periods, n_stocks),  # 动量因子
    'value': np.random.randn(n_periods, n_stocks),      # 价值因子
    'volatility': np.random.randn(n_periods, n_stocks), # 波动率因子
}

# 模拟收益（假设momentum是有效因子）
returns = 0.02 * factor_data['momentum'] + 0.01 * np.random.randn(n_periods, n_stocks)
return_df = pd.DataFrame({'ret': returns.mean(axis=1)})

factor_df = pd.DataFrame({k: v.mean(axis=1) for k, v in factor_data.items()})
ic_result = factor_rank_ic(factor_df, return_df)
print("因子IC/IR评估:")
print(ic_result.round(4))
```

## 2. 因子相关性矩阵

```python
def factor_corr_matrix(factor_data_dict):
    """计算因子之间的截面相关性（剔除冗余因子）"""
    period_corr = []
    n_factors = len(factor_data_dict)
    
    for t in range(len(list(factor_data_dict.values())[0])):
        corr_t = np.ones((n_factors, n_factors))
        names = list(factor_data_dict.keys())
        for i in range(n_factors):
            for j in range(i+1, n_factors):
                fi = factor_data_dict[names[i]][t]
                fj = factor_data_dict[names[j]][t]
                mask = ~(np.isnan(fi) | np.isnan(fj))
                if mask.sum() > 5:
                    c, _ = spearmanr(fi[mask], fj[mask])
                    corr_t[i, j] = c
                    corr_t[j, i] = c
        period_corr.append(corr_t)
    
    avg_corr = np.mean(period_corr, axis=0)
    print("因子平均截面相关性:")
    for i in range(n_factors):
        for j in range(i+1, n_factors):
            print(f"  {names[i]} vs {names[j]}: {avg_corr[i,j]:.4f}")
    
    # 剔除高度相关因子（|corr| > 0.7）
    high_corr_pairs = []
    for i in range(n_factors):
        for j in range(i+1, n_factors):
            if abs(avg_corr[i, j]) > 0.7:
                high_corr_pairs.append((names[i], names[j], avg_corr[i, j]))
    
    return avg_corr, high_corr_pairs

avg_corr, high_pairs = factor_corr_matrix(factor_data)
if high_pairs:
    print("\n高度相关因子对（考虑剔除):")
    for p in high_pairs:
        print(f"  {p[0]} vs {p[1]}: {p[2]:.4f}")
```

## 3. 因子合并方法

```python
class FactorCombiner:
    """多种因子合并方法"""
    
    @staticmethod
    def equal_weight(factors):
        """等权合并"""
        return np.mean(factors, axis=0)
    
    @staticmethod
    def ic_weight(factors, ic_values):
        """IC加权：用历史IC均值作为权重"""
        weights = np.array([ic_values.get(f, 0.01) for f in factors])
        weights = weights / weights.sum()
        return weights
    
    @staticmethod
    def icir_weight(factors, ic_values, ir_values):
        """ICIR加权：用IC均值 * IR 作为权重"""
        weights = np.array([
            ic_values.get(f, 0.01) * ir_values.get(f, 0.1)
            for f in factors
        ])
        weights = weights / weights.sum()
        return weights
    
    @staticmethod
    def ma_weight(factors, ic_history, half_life=60):
        """移动平均加权：近期IC更高的因子权重更大"""
        n_factors = len(factors)
        ic_ma = []
        for i in range(n_factors):
            ic_series = ic_history[:, i]
            w = np.exp(-np.arange(len(ic_series))[::-1] / half_life)
            ic_ma.append(np.average(ic_series, weights=w))
        
        weights = np.array(ic_ma)
        weights = np.maximum(weights, 0)  # 负IC因子剔除
        if weights.sum() > 0:
            weights = weights / weights.sum()
        return weights

# 测试
combiner = FactorCombiner()

# 模拟因子序列
np.random.seed(42)
n_factors = 3
n_periods = 120

factor_vals = np.random.randn(n_periods, n_factors)
ic_history = np.random.randn(n_periods, n_factors) * 0.1 + 0.05  # 平均IC 0.05

ic_means = {f'factor_{i}': np.mean(ic_history[:, i]) for i in range(n_factors)}
ir_vals = {f'factor_{i}': np.mean(ic_history[:, i]) / (np.std(ic_history[:, i]) + 1e-10) 
           for i in range(n_factors)}

# 计算各种权重
equal_w = combiner.equal_weight(factor_vals)  # 这里返回复合分数
ic_w = combiner.ic_weight([f'factor_{i}' for i in range(n_factors)], ic_means)
icir_w = combiner.icir_weight([f'factor_{i}' for i in range(n_factors)], ic_means, ir_vals)
ma_w = combiner.ma_weight([f'factor_{i}' for i in range(n_factors)], ic_history)

print("因子权重对比:")
print(f"  IC加权: {np.round(ic_w, 4)}")
print(f"  ICIR加权: {np.round(icir_w, 4)}")
print(f"  MA加权: {np.round(ma_w, 4)}")
```

## 4. 因子择时

```python
def factor_timing(factor_returns, lookback=60):
    """简单的因子择时：用近期表现调整权重
    
    思路：因子也有好坏周期，用滚动IR判断当前因子有效性
    """
    n_periods, n_factors = factor_returns.shape
    dynamic_weights = np.zeros((n_periods, n_factors))
    
    for t in range(lookback, n_periods):
        # 滚动窗口的IR
        window = factor_returns[t-lookback:t]
        rolling_ic = np.mean(window, axis=0)
        rolling_std = np.std(window, axis=0) + 1e-10
        rolling_ir = rolling_ic / rolling_std
        
        # 只用正IR因子，负的设为零
        weights = np.maximum(rolling_ir, 0)
        if weights.sum() > 0:
            weights = weights / weights.sum()
        else:
            weights = np.ones(n_factors) / n_factors
        
        dynamic_weights[t] = weights
    
    # 对比静态权重
    static_weight = np.ones(n_factors) / n_factors
    static_perf = factor_returns @ static_weight
    dynamic_perf = np.sum(factor_returns * dynamic_weights, axis=1)
    
    print("因子择时效果:")
    print(f"  静态组合年化收益: {static_perf.mean() * 252:.4f}")
    print(f"  动态择时年化收益: {dynamic_perf.mean() * 252:.4f}")
    print(f"  动态IR: {dynamic_perf.mean() / (dynamic_perf.std() + 1e-10):.4f}")
    
    return dynamic_weights

# 测试
factor_ret = np.random.randn(n_periods, 3) * 0.02
factor_ret[:, 0] += 0.005  # 因子1长期有效
factor_ret[:60, 1] += 0.008  # 因子2前60期有效
factor_ret[60:, 2] += 0.006  # 因子3后60期有效

weights = factor_timing(factor_ret)
```

## 5. PCA合成因子

```python
from sklearn.decomposition import PCA

def pca_factor_synthesis(raw_factors, n_components=None):
    """用PCA从多个因子中提取主成分因子
    
    优点：
    - 自动去相关
    - 降维减少噪声
    - 第一主成分通常是"市场共识因子"
    """
    n_samples, n_features = raw_factors.shape
    if n_components is None:
        n_components = min(n_features, 5)
    
    # 标准化
    factor_mean = np.nanmean(raw_factors, axis=0)
    factor_std = np.nanstd(raw_factors, axis=0)
    factors_std = (raw_factors - factor_mean) / (factor_std + 1e-10)
    
    # 填充NaN
    factors_std = np.nan_to_num(factors_std, nan=0.0)
    
    pca = PCA(n_components=n_components)
    pca_factors = pca.fit_transform(factors_std)
    
    # 解释方差
    explained_ratio = pca.explained_variance_ratio_
    cum_ratio = np.cumsum(explained_ratio)
    
    print(f"PCA因子合成 (原始{n_features}维 → {n_components}维):")
    for i in range(n_components):
        print(f"  PC{i+1}: {explained_ratio[i]:.2%} (累计{cum_ratio[i]:.2%})")
    
    # 看第一主成分的原始因子权重
    pc1_weights = pca.components_[0]
    print(f"\n第一主成分的因子权重:")
    for i, w in enumerate(pc1_weights):
        print(f"  Factor_{i}: {w:.4f}")
    
    return pca_factors, pca

# 测试
np.random.seed(42)
n_samples = 1000
n_raw_factors = 20

# 模拟原始因子：10个有效 + 10个噪声
raw = np.zeros((n_samples, n_raw_factors))
for i in range(10):
    raw[:, i] = np.random.randn(n_samples) + 0.3 * np.sin(i + np.arange(n_samples) * 0.1)
for i in range(10, 20):
    raw[:, i] = np.random.randn(n_samples) * 0.5  # 噪声

pca_factors, pca_model = pca_factor_synthesis(raw, 5)

# 用合成因子做预测
target = 0.5 * raw[:, 0] + 0.3 * raw[:, 2] + np.random.randn(n_samples) * 0.2
from sklearn.linear_model import LinearRegression

# 原始因子
lr_raw = LinearRegression().fit(raw, target)
r2_raw = lr_raw.score(raw, target)

# PCA合成因子
lr_pca = LinearRegression().fit(pca_factors[:, :3], target)
r2_pca = lr_pca.score(pca_factors[:, :3], target)

print(f"\n预测性能对比:")
print(f"  原始20因子 R²: {r2_raw:.4f}")
print(f"  PCA前3因子 R²: {r2_pca:.4f}")
print(f"  PCA因子数只有原始15%，保留 {(r2_pca/r2_raw)*100:.1f}% 的解释力")
```

## 6. 全流程：多因子选股评分系统

```python
class MultiFactorScoring:
    """完整的多因子选股评分系统"""
    
    def __init__(self, factors_config=None):
        """
        factors_config: {
            '因子名': {'weight': 0.3, 'direction': 1, 'method': 'zscore'},
            ...
        }
        """
        self.factors_config = factors_config or {}
        self.performance_history = []
    
    def add_factor(self, name, weight, direction=1, method='zscore'):
        """
        direction: 1=因子值越大越好, -1=越小越好
        method: 'zscore' / 'rank' / 'percentile'
        """
        self.factors_config[name] = {
            'weight': weight,
            'direction': direction,
            'method': method
        }
    
    def normalize_factor(self, factor_values, method='zscore'):
        """因子标准化"""
        mask = ~np.isnan(factor_values)
        normalized = np.full_like(factor_values, np.nan)
        
        if method == 'zscore':
            mean = np.nanmean(factor_values)
            std = np.nanstd(factor_values)
            normalized[mask] = (factor_values[mask] - mean) / (std + 1e-10)
        
        elif method == 'rank':
            # 排名标准化 [0, 1]
            ranks = np.argsort(np.argsort(factor_values))
            normalized[mask] = ranks[mask] / (mask.sum() - 1)
        
        elif method == 'percentile':
            # 百分位数 [0, 1]
            from scipy.stats import percentileofscore
            for i in range(len(factor_values)):
                if not np.isnan(factor_values[i]):
                    normalized[i] = percentileofscore(
                        factor_values[mask], factor_values[i]) / 100.0
        
        # 极端值截断（3倍标准差）
        if method == 'zscore':
            normalized = np.clip(normalized, -3, 3)
        
        return normalized
    
    def score_one_period(self, factor_data):
        """一期评分"""
        if not self.factors_config:
            raise ValueError("请先使用 add_factor() 添加因子配置")
        
        n_stocks = len(factor_data[list(factor_data.keys())[0]])
        scores = np.zeros(n_stocks)
        total_weight = sum(cfg['weight'] for cfg in self.factors_config.values())
        
        for name, cfg in self.factors_config.items():
            raw_values = factor_data[name]
            normalized = self.normalize_factor(raw_values, cfg['method'])
            
            # 方向调整
            normalized *= cfg['direction']
            
            # 加权求和
            scores += normalized * cfg['weight'] / total_weight
        
        return scores
    
    def backtest(self, factor_data_dict_list, forward_returns_list):
        """多期回测"""
        period_scores = []
        for period_data in factor_data_dict_list:
            score = self.score_one_period(period_data)
            period_scores.append(score)
        
        period_scores = np.array(period_scores)
        
        # 分10组考察单调性
        n_periods, n_stocks = period_scores.shape
        group_returns = np.zeros((n_periods, 10))
        
        for t in range(n_periods):
            score = period_scores[t]
            ret = forward_returns_list[t]
            mask = ~(np.isnan(score) | np.isnan(ret))
            
            if mask.sum() >= 10:
                score_valid = score[mask]
                ret_valid = ret[mask]
                
                # 分10组
                deciles = pd.qcut(score_valid, 10, labels=False)
                for g in range(10):
                    group_mask = deciles == g
                    if group_mask.sum() > 0:
                        group_returns[t, g] = ret_valid[group_mask].mean()
        
        # 多空收益（Top组 - Bottom组）
        long_short = group_returns[:, 0] - group_returns[:, -1]
        annual_ret = long_short.mean() * 252
        sharpe = long_short.mean() / (long_short.std() + 1e-10) * np.sqrt(252)
        win_rate = np.mean(long_short > 0)
        
        print("多因子评分回测结果:")
        print(f"  年化多空收益: {annual_ret:.2%}")
        print(f"  夏普比率: {sharpe:.2f}")
        print(f"  胜率: {win_rate:.2%}")
        
        # 单调性得分（各组均值是否单调）
        group_avg = np.nanmean(group_returns, axis=0)
        rank_corr, _ = spearmanr(np.arange(10), group_avg)
        print(f"  分组单调性秩相关: {rank_corr:.4f}")
        
        return {
            'period_scores': period_scores,
            'group_returns': group_returns,
            'long_short': long_short,
            'metrics': {
                'annual_return': annual_ret,
                'sharpe': sharpe,
                'win_rate': win_rate,
                'monotonicity': rank_corr
            }
        }

# 测试完整评分系统
np.random.seed(42)
n_periods = 100
n_stocks = 200

scorer = MultiFactorScoring()
scorer.add_factor('momentum', weight=0.3, direction=1)
scorer.add_factor('value', weight=0.3, direction=1)
scorer.add_factor('low_vol', weight=0.2, direction=-1)  # 低波动好
scorer.add_factor('quality', weight=0.2, direction=1)

# 模拟数据
factor_data_list = []
forward_ret_list = []

for t in range(n_periods):
    factor_data = {}
    # 只有momentum是有效因子
    factor_data['momentum'] = np.random.randn(n_stocks)
    factor_data['value'] = np.random.randn(n_stocks) * 0.5
    factor_data['low_vol'] = np.random.randn(n_stocks) * 0.3
    factor_data['quality'] = np.random.randn(n_stocks) * 0.3
    
    # 收益只与momentum相关
    forward_ret = 0.03 * factor_data['momentum'] + np.random.randn(n_stocks) * 0.02
    
    factor_data_list.append(factor_data)
    forward_ret_list.append(forward_ret)

result = scorer.backtest(factor_data_list, forward_ret_list)
```

## 总结

| 方法 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| 等权合并 | 因子间不相关时 | 简单、稳定 | 被劣质因子拖累 |
| IC加权 | 有充分历史数据 | 客观、自适应 | IC不稳定时失效 |
| ICIR加权 | 因子有效性波动大 | 兼顾IC和稳定性 | 需要较长历史 |
| 因子择时 | 因子有明显周期 | 动态最优 | 过拟合风险 |
| PCA合成 | 因子高度相关时 | 去相关、降噪 | 可解释性差 |
