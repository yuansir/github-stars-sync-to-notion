# GitHub Stars 同步到 Notion

这是一个 Python 脚本，用于将你的 GitHub Starred 仓库自动同步到 Notion 数据库。它可以帮助你更好地管理和组织你的 GitHub Stars。

## 功能特点

- 自动同步 GitHub Starred 仓库到 Notion 数据库
- 记录仓库的基本信息（名称、描述、URL、语言等）
- 支持仓库主题标签（Topics）
- 记录 Star 时间
- 自动处理分页和重试
- 完整的错误处理和日志记录

## 前置要求

1. Python 3.9 或更高版本
2. Notion 账号和工作区
3. GitHub 账号

## 设置步骤

### 1. Notion 设置

1. 创建 Notion 集成
   - 访问 [Notion Integrations](https://www.notion.so/my-integrations)
   - 点击 "New integration"
   - 填写集成名称（例如："GitHub Stars Sync"）
   - 记录生成的 **Notion Token**（以 "secret_" 开头）

2. 创建 Notion 数据库
   - 在 Notion 中创建一个新的数据库页面
   - 添加以下属性（属性名称必须完全匹配）：
     - `Name`（标题类型）
     - `GitHub Repo ID`（文本类型）
     - `Description`（文本类型）
     - `URL`（文本类型）
     - `Language`（选择类型）
     - `Stars`（数字类型）
     - `Topics`（多选类型）
     - `Starred At`（日期类型）
   - 从数据库 URL 中复制 **Database ID**（32 位字符）
   - 点击右上角 "Share" > "Add connections"，添加你刚创建的集成

### 2. GitHub 设置

1. 创建 GitHub Token
   - 访问 [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
   - 点击 "Generate new token" > "Generate new token (classic)"
   - 选择以下权限：
     - `read:user`
     - `public_repo`
   - 生成并复制 **GitHub Token**

### 3. 项目设置

1. 克隆项目
   ```bash
   git clone https://github.com/your-username/githubstars-sync-to-notion.git
   cd githubstars-sync-to-notion
   ```

2. 创建虚拟环境
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # 或
   .venv\Scripts\activate  # Windows
   ```

3. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量
   - 在项目根目录创建 `.env` 文件
   - 添加以下内容（替换为你的实际值）：
   ```
   NOTION_TOKEN="secret_xxx"
   NOTION_DATABASE_ID="xxx"
   GITHUB_TOKEN="ghp_xxx"
   ```

## 使用方法

1. 测试连接
   ```bash
   python test_connection.py
   ```

2. 运行同步
   ```bash
   python main.py
   ```

## 注意事项

- 首次运行时会同步所有已 Star 的仓库，可能需要一些时间
- 建议定期运行以保持同步
- 如果遇到 API 限制，脚本会自动等待并重试
- 所有操作都会记录在日志中

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License 