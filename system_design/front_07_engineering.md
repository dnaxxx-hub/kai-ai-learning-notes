# 前端工程化

> 日期：2026-05-07 20:36 | 课程：前端路线 Phase 4-1
> 目标：理解"一个前端项目从零到上线要经历什么"

## 一个完整前端项目的工具链

```
代码 (JS/TS/JSX/CSS) 
  → 打包 (Vite)
    → 转译 (Babel/SWC)
      → 压缩 (Terser)
        → 部署 (Vercel/Netlify...)
```

## 构建工具

### Vite（当前主流）

```javascript
// 旧的 Webpack: 整个项目打包再启动 → 慢
// Vite: 用原生ESM → 按需编译 → 瞬间启动

// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    minify: 'terser',
    sourcemap: true,
  },
});
```

### Webpack（老牌，但被Vite替代中）

```javascript
// 配置复杂（曾被称为"Webpack配置比写业务代码还难"）
// module.exports = { entry: ..., output: ..., plugins: [...], loaders: [...] }
// Vite出来后，新项目基本不用Webpack了
```

## 代码质量

### ESLint（代码规范）

```javascript
// 统一代码风格
// 规则示例：
{
  "rules": {
    "no-unused-vars": "error",    // 未使用的变量 → 报错
    "no-console": "warn",         // console.log → 警告
    "react-hooks/exhaustive-deps": "warn",  // useEffect依赖检查
  }
}
```

### Prettier（自动格式化）

```javascript
// 代码格式（缩进/引号/分号/换行...）
// 和ESLint配合: ESLint管"逻辑规范"，Prettier管"格式规范"
```

## 测试金字塔

```javascript
// 单元测试 (jest/vitest) → 测试单个函数/组件
// 集成测试 (Testing Library) → 测试组件交互
// E2E测试 (Playwright/Cypress) → 模拟用户操作

// 推荐比例: 70% 单元 + 20% 集成 + 10% E2E

// 一个简单测试:
test('Counter increments', () => {
  render(<Counter />);
  const button = screen.getByText('+1');
  fireEvent.click(button);
  expect(screen.getByText('1')).toBeInTheDocument();
});
```

## 部署

### Vercel（最流行的React部署平台）

```
1. git push → 自动部署
2. 自动SSL证书
3. 自动CDN
4. Preview Deployments（每个PR都有自己的预览URL）
5. Serverless API（Next.js自动部署API路由）

其他: Netlify / Railway / AWS Amplify / Cloudflare Pages
```

### CI/CD

```yaml
# GitHub Actions 示例
name: Deploy
on: push

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm test
      - run: npm run build
      
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - run: npx vercel --prod  # 测试通过 → 自动部署
```

## 现代前端项目模板

```bash
# 创建一个新项目（2026年标准）
npx create-next-app@latest my-app --typescript --tailwind

# 目录结构
my-app/
├── app/
│   ├── layout.tsx          # 全局布局
│   ├── page.tsx            # 首页
│   ├── about/page.tsx      # 关于页
│   └── api/posts/route.ts  # API路由
├── components/              # 组件
├── lib/                     # 工具函数
├── public/                  # 静态资源
├── tailwind.config.ts       # Tailwind配置
└── package.json
```

## 今日收获
- 构建工具: Vite > Webpack（新项目用Vite）
- ESLint + Prettier = 前端标配
- 测试: 单元 > 集成 > E2E
- Vercel = 一键部署
- **现代前端项目 = Next.js + TypeScript + TailwindCSS + Vite + ESLint + GitHub Actions**
