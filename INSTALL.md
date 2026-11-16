# 安装与接入

## 前置条件

- Python 3.10+
- `pip install -r requirements.txt`
- PandaData 账号（仅现拉席位数据时需要）

## 通用步骤

```bash
git clone https://github.com/quantskills/skill-q4-seat-alpha.git
cd skill-q4-seat-alpha
pip install -r requirements.txt
python scripts/test.py
```

凭据通过环境变量注入：

```bash
# Windows cmd
set PANDA_DATA_USERNAME=your_phone
set PANDA_DATA_PASSWORD=your_password
set PANDA_DATA_BASE_URL=http://pandadata.pandaaiquant.com

# macOS / Linux
export PANDA_DATA_USERNAME=your_phone
export PANDA_DATA_PASSWORD=your_password
export PANDA_DATA_BASE_URL=http://pandadata.pandaaiquant.com
```

## Claude Code

放到 `.claude/skills/seat-alpha/`，或直接读取当前目录的 `SKILL.md`。

## Codex

保留仓库根目录的 `SKILL.md`，按 Codex skill 发现规则读取：

```bash
python scripts/factor.py --data-dir /path/to/q4_data
```

## Cursor

复制到 `.cursor/skills/seat-alpha/` 并加载 `agents/cursor-rule.mdc`。

## Hermes / OpenClaw

使用 `agents/portable-loader.md`，把 `<SEAT_ALPHA_SKILL_ROOT>` 替换为本地绝对路径。

## 验证

```bash
python scripts/test.py
python scripts/validate.py --data-dir /path/to/q4_data
```

`scripts/validate.py` 输出四项 PASS/FAIL；任一项 FAIL 时退出码为 1。测试与验真均可使用仓库自带的真实数据切片（`tests/fixtures/`）与基线（`references/baseline/`）。
