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
