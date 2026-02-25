"""全局测试配置：确保所有测试在测试模式下运行。"""

import os

# 在任何模块导入之前设置 TESTING 环境变量，
# 防止 app.main 启动事件创建后台任务。
os.environ["TESTING"] = "1"
