# GitHub 项目权限与分支保护设置指南

作为小组大作业的项目负责人，为了防止组员误操作导致代码覆盖或主分支崩溃，你需要在 GitHub 网页端进行权限收拢。以下是为你量身定制的最佳实践方案。

---

## 步骤一：邀请组员加入项目 (Collaborators)

1. 进入你新建的 GitHub 仓库页面。
2. 点击上方的 **Settings**（设置）选项卡。
3. 在左侧菜单中找到 **Collaborators**（协作者）。
4. 点击 **Add people**，输入你 3 位组员的 GitHub 用户名或注册邮箱，将他们邀请进仓库。
   - 注意：此时他们默认拥有直接向所有分支推送 (Push) 甚至删除文件的最高写权限。如果不加以限制，极易发生灾难。

---

## 步骤二：为主分支 (`main`) 加上“防弹衣”

我们的核心诉求是：**仅限你一人可以修改/合并 `main` 版本，其他组员只能提交合并请求 (Pull Request)**。

1. 在 **Settings** 页面，点击左侧菜单的 **Branches**（分支）。
2. 在 Branch protection rules（分支保护规则）板块，点击 **Add branch protection rule**。
3. **Branch name pattern（分支名匹配）**：在输入框内输入 `main`。
4. **勾选保护选项（核心关键）**：
   
   - [x] **Require a pull request before merging** 
     *(合并前必须提交 PR：组员无法再通过终端 `git push origin main` 强行推送代码，只能在网页上发起合并申请)*。
     - 在展开的子菜单中，勾选 **Require approvals**，并将数量设置为 `1`。
     *(这代表所有的代码合并必须经过至少 1 个人的审批，作为负责人的你，自然就是这个唯一拥有最终裁定权的人)*。

   - [x] **Require conversation resolution before merging**
     *(要求在合并前解决所有的代码评论反馈，如果你在 Review 代码时给组员留了修改意见，他必须改完才能合并)*。

   - [x] **Do not allow bypassing the above settings**
     *(包括你自己在内的管理员也不能绕过这些规则强行提交，防止你手滑出错)*。

   - [x] **Restrict who can push to matching branches** 
     *(限制谁可以直接推送到此分支：勾选后，在搜索框中搜索你自己的 GitHub 用户名并添加。这样除了你以外的任何人，连 Push 按钮都会变成灰色。注：如果是个人免费版私有仓库，此高级选项可能受限，但上方强制 PR 的规则已足以防范误操作)*。

5. 滚动到页面最下方，点击绿色的 **Create** 按钮保存。

---

## 步骤三：日常工作流如何运转？

配置好上述规则后，你们小组 4 人的日常合作将变成以下安全模式：

1. **组员视角**：
   - 组员每天只能将代码 Push 到自己新建的分支，例如 `feat/frontend-calendar`。
   - 组员在网页端点击 **New Pull Request**，申请把代码合并到 `dev` 或 `main`。
   - 组员的代码如果与现有代码有冲突，GitHub 会拒绝合并，要求组员自己在本地解决完再发。
2. **负责人视角**：
   - 组员发起 PR 后，你会收到邮件通知。
   - 你点开 PR 详情，查看 **Files changed**（文件变动）。如果是简单的修改，甚至可以直接发给 AI 让它帮忙过一遍有没有明显的 Bug。
   - 如果一切顺利，你点击绿色的 **Merge pull request** 按钮。
   - 如果代码很糟糕，你可以点击 **Review changes**，留下修改意见并选择 **Request changes**（打回重做）。

按照以上设置，`main` 主分支将变成一道铜墙铁壁，只有经过你亲自点头的优质代码才能进入，从此告别混乱！