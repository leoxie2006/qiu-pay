# PR 规范

## 分支及提交
- 从最新 main 创建 `codex/<type>-<topic>`；禁止直接在 main 开发。
- Conventional Commits：`fix: 中文说明`、`feat:`、`test:`、`docs:`、`ci:`。
- 每个 PR 聚焦可审查变更；紧急安全修复可以同时补回归和发布护栏。
- 不提交 `.env`、私钥、数据库、真实订单和生产签名；生产证据保存到访问受控位置。

## 审查及合并门槛
1. 描述现象、根因、影响、兼容性、测试和回滚。
2. CI 的 `checks`、`image` 必须成功；至少一位维护者 review。
3. 建议 main 开启 branch protection：要求 PR、review、上述状态检查；禁止 force push。
   本文仅规定流程，不代表已在 GitHub 启用保护。
4. 采用 squash merge；通过审查后合并并删除临时分支。
5. PR CI 只测试及构建，不读取部署 SSH 密钥、不发布、不部署。
6. main CI 全绿后发布 `sha-<commit>` 镜像，部署必须使用 `@sha256:`。
7. demo 自动部署和生产发布分离；生产另设人工审批，不由此 demo workflow 触发。

## 安全修复的证据用语
明确区分“源码确认”“隔离测试实证”“运行镜像实证”和“生产 HTTP 验证”。
测试签名有效不等于商户已发货；源码相同不等于生产部署的版本相同。

## Release 更新说明

Release 面向安装和使用 Qiu-Pay 的用户，正文只列本版本修复的问题、新增功能，以及安装或更新步骤。用具体变化描述问题，例如“修复容器与主机时区不一致”，不要写审查过程、测试数量、CI 运行记录、部署安排或内部漏洞编号。

每个稳定版本在 `docs/releases/<tag>.md` 提供更新说明；未准备说明时发布流程停止，不以 PR/commit 列表代替。镜像地址、必要配置和升级注意事项放在安装与更新部分。commit、digest、平台等可追溯信息由 `release-manifest.json` 附件保存。

后台使用文档由 `app/routes/docs.py` 的 `USER_DOCS` 明确登记。发布说明、PR 规范和维护者部署记录不加入该清单。
