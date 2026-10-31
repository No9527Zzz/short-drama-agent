# Short Drama Agent

本项目是一个本地运行的短剧生成 Agent，面向 **2D 动态漫画短剧**制作。

项目通过浏览器 Web 界面操作，管理“剧本 → 整剧规划 → 角色与场景 → 单集剧本 → 分镜 → 图片和配音 → 视频合成”的多集短剧流程。

## 当前制作规格

- 每部短剧：80 集
- 每集时长：60 秒
- 画面比例：9:16
- 成片分辨率：1080 × 1920
- 帧率：25 fps
- 输出格式：MP4 / H.264 / AAC
- 字幕格式：SRT，可通过 FFmpeg 烧录

## 已实现功能

### 项目、剧本和规划

- 创建项目，支持完整剧本、小说原文、故事创意三种入口
- 粘贴文本或导入 txt、md 文件
- 生成 80 集整剧规划初稿
- 编辑分集标题、梗概、冲突和结尾悬念
- 规则解析角色、场景和对白
- 生成并编辑单集剧本和场景

### 角色、场景和分镜

- 角色和场景资产管理
- 编辑身份、外貌、音色、时间、天气和视觉描述
- 生成单集分镜草稿
- 默认 6 个镜头，总时长 60 秒
- 编辑景别、机位、时长、画面、动作和对白
- 上传镜头关键画面并预览

### 任务和生成

- 后台 Worker、排队、进度、失败、取消、重试和重启恢复
- Windows SAPI 中文配音并生成 WAV
- SRT 字幕生成
- FFmpeg 动态漫画合成代码
- 图片和 TTS Provider 接口
- 跨集连续性检查和批量合成任务

## 技术架构

浏览器 Web 界面 → FastAPI → SQLite、本地媒体目录、后台 Worker。

主要代码位于 app 目录，静态页面位于 static 目录。

## 环境与启动

环境要求：Windows 10/11、Python 3.15、FFmpeg。进入项目目录后执行：

    cd D:\short_drama
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python run.py

浏览器地址：http://127.0.0.1:8000

API 文档：http://127.0.0.1:8000/docs

## Provider 配置

默认使用 Windows SAPI：

    $env:SHORT_DRAMA_TTS_PROVIDER = "sapi"

图片模型通过命令模板接入：

    $env:SHORT_DRAMA_IMAGE_COMMAND = "python C:\path\generate.py {output}"

命令模板支持 {prompt}、{output} 和 {reference} 参数，可接入 ComfyUI、Stable Diffusion WebUI 或自定义推理脚本。

## 当前限制

- 80 集规划和剧本解析目前以结构化规则为主。
- 小说改编和创意扩写尚未接入本地语言模型。
- FFmpeg 需要在本机安装后才能实际导出 MP4。
- 角色跨镜头一致性、人物状态追踪和高级混音仍需完善。
- 完整版本历史、差异对比、恢复和项目备份仍在开发。

## Git 管理

    git add .
    git commit -m "说明本次修改"
    git push

远程仓库：https://github.com/No9527Zzz/short-drama-agent.git

## 开发原则

- 业务流程不绑定具体模型。
- 原始内容、剧本、分镜和素材分开管理。
- 生成任务必须可追踪、可失败和可重试。
- 已确认内容不直接覆盖。
- 每个阶段支持人工审核。

