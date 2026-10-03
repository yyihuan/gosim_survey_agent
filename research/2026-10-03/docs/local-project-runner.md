# 本地项目运行 / Local project runner

> 2026-09-27：正式比赛 `online` 不开放本地会话，只评测完整项目；本页仅适用于开启了本地会话的阶段。
> Local sessions are disabled for the formal `online` phase (complete projects only).

需要 Python 3.12；默认使用 Docker 运行完整项目。也可以用 `--native` 在自己的电脑上直接运行自己信任的项目。
项目语言不限，Python 只是与比赛服务器通信的运行器。

1. 在网站「提交」页选择本地运行，点击「启动本地 CSV 会话」。
2. 等待任务启动，打开对应记录中的「本地运行信息」。下载并解压运行器。
3. 项目根目录应包含 `observer.project.json`，其中 `run` 和 `build` 是参数数组。
   可以使用已经在网站检查过的运行设置；不需要把项目改写成 Python。
4. 在运行器目录运行网页给出的命令，替换项目目录。提示后粘贴本次临时凭证；输入不回显。
5. 完成后，将生成的 `decisions.csv` 上传到同一条评测记录。不要修改 CSV。

```sh
python3 -m project_platform.local --project /path/to/project --session-url https://PROJECT.supabase.co/functions/v1/observer-session --model-base-url https://PROJECT.supabase.co/functions/v1/observer-model/v1 --output decisions.csv
```

如果不用 Docker，在命令后加 `--native`。这种模式会直接执行项目的构建与启动命令，只用于自己的项目。
模型可不使用；使用时读取 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY`。后者只对本次运行有效，不是上游模型密钥。
运行器只接收服务器当前公开的信息，无法下载未来天气或异常答案。

结束后只需重新导出时，在同一条命令后加 `--export-only`，不重新运行智能体。
已有输出文件不会覆盖，请改用新的 `--output` 文件名。临时凭证不要提交到仓库或写入项目 ZIP。
导出只包含官方实际执行的决策；运行器核对文件指纹后才写入 CSV。

For English-speaking teams: select a local session on the Submit page, download
and extract this runner, and execute the command above. Your complete project
must include `observer.project.json`; any language can implement its JSON-Lines
interface. Docker is the default. `--native` explicitly runs your own trusted
project directly on your machine. Paste the temporary run credential at the
hidden prompt, then upload the verified CSV to the matching session. Use
`--export-only` to recover a finished trace without executing your agent again.
