# 背景
AnkiRepository 插件是 Anki 与 Notion 之间同步笔记的插件,该插件的V1.0版本见AnkiRepository_V1.0文件夹，能够实现readme_old.md中要求的全部功能。

# 问题待解决

AnkiRepository_V1.0 这个文件夹是重构后的插件代码的工作目录，重构后的插件能够解决旧版本插件的以下问题。
## **1重构代码，改为OOP**
  需要和AnkiRepository_V1.0一样能实现readme_old.md 中要求的全部功能。
  需要提高代码的可维护性和可拓展性。减少代码之间的耦合和代码重复，增加抽象和接口。加入多进程，同时避免阻塞主进程导致anki卡顿。
  可能需要使用策略模式，工厂模式和观察者模式
  未来可能还需要拓展插件，实现 Anki 与 Get 笔记之间的互导。

重构路线建议：
- 先建立核心接口（Strategy）
- 将现有函数拆分为领域对象（Note, Config等）
- 用依赖注入替换硬编码的配置访问
- 用装饰器统一处理异常和日志
- 最后重构UI层与核心逻辑的解耦

## **2解决优化其他问题**  
- **导入导出notion之外的其他平台**  
  比如导入导出到get笔记。
  
- **导入导出笔记的性能优化**  
  导入导出笔记时，不应导致 Anki 卡顿。导入应是一个新的进程，不应阻塞主进程。

- **模板销毁情况下的恢复测试**  
  测试在模板被销毁的情况下，不能使用 Notion 中的笔记来恢复原始卡片。因此需添加是否将模板导入Notion备份以便将来恢复模板的选项，如果用户勾选，则导入笔记时自动判断是否需要导入模板（如果已有，则不重复导入）。模板单独占一条笔记（想办法通过代码实现在notion中自动隐藏这条笔记）。如果 Anki 中模板名无法找到笔记模板，应去找 Notion 中的模板笔记。

- **Notion 正文中重复卡片内容**  
  在 Notion 正文中重复卡片内容，方便搜索（用户自己添加的 Notion 正文应在这之后）。

- **暂停笔记导入 Anki 的到期日问题**  
  暂停笔记导入 Anki 时，到期日不对，为 2024 年 8 月 28 日，实际应改为今日更合适（无法设置过去为到期日）。

- **多媒体文件转化为 URL**  
  提供替换本地的.jpg文件和.png文件为 URL的功能。

- **重复笔记问题**  
  首字段都为空且模板名都相同的情况下，也是重复笔记——可能无法解决。