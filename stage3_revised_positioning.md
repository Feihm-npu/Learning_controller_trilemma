# Stage-3 修订定位：从 plausible-state safety filtering 到 certificate lifecycle gate

> 状态：贡献定位修订 v1（2026-06-30）。触发原因：`Safety of Linear Systems under Severe Sensor Attacks` 已覆盖 severe sensor attack 下的 plausible-state characterization + CBF/QP safety filter，因此本方向必须把新意收紧到 online-updated learning controller 的证书生命周期。

## 1. 必须承认的 baseline

`Safety of Linear Systems under Severe Sensor Attacks` 已经处理了一个非常接近的固定控制问题：

1. 攻击者可任意 spoof 若干传感器。
2. secure state reconstruction 可不唯一。
3. 论文刻画所有 plausible states。
4. 论文基于 CBF/QP 在 offline/online phases 设计 safety filter。
5. 结论是在 severe sensor attacks 下仍可在一定条件中 enforce safety。

因此，本项目不能把以下内容作为主要新意：

1. FDI/sensor attack 会导致状态不可区分。
2. 证书必须对 plausible state set 成立。
3. CBF/QP 可用于 plausible state set 上的安全过滤。
4. 当 plausible state set 过大时 safety filter 可能不可行。

这些都应作为已有控制安全文献的基础或 baseline。

## 2. 修订后的精确 gap

修订后的 gap 是：

> 已有 severe sensor attack safety filters 说明固定控制器在状态不唯一时如何安全过滤；但它们没有回答，当控制器在部署后根据同一被攻击历史继续更新时，安全证书如何随更新保持、何时必须撤销、何时必须冻结 learning。

换句话说，核心对象不是单个 safety filter，而是证书在在线更新算子下的生命周期：

$$
(\Gamma_t,\theta_t,h_t)\xrightarrow{U}(\Gamma_{t+1},\theta_{t+1})
$$

其中 $h_t$ 可能被 FDI 污染，且 $U$ 会改变控制器 action map。

## 3. 修订后的主定理形态

设已有某种 severe-attack-aware safety filter 或证书机制能够从历史 $h$ 构造状态歧义集 $X_{\mathcal A}(h)$ 和 certified kernel $K_\Gamma(h)$。这部分不作为新贡献。

我们的 theorem 应写成：

**Certificate Lifecycle Gate Theorem.** 对任何历史依赖的 online-updated controller，如果它在历史 $h$ 上执行非平凡更新

$$
\theta_{t+1}=U(\theta_t,h),\quad \pi_{\theta_{t+1}}\not\equiv \pi_{\theta_t},
$$

并继续声称更新后控制器处于 sound certified operation，则必须满足：

$$
\pi_{\theta_{t+1}}(h)\in K_\Gamma(h).
$$

更一般地，对未来历史分布或 reachable ambiguity sets，需要满足：

$$
\forall h'\in\mathcal H_{\mathcal A}(h,\theta_{t+1}),\quad
\pi_{\theta_{t+1}}(h')\in K_\Gamma(h').
$$

若 $K_\Gamma(h)=\emptyset$，则 sound 机制必须满足：

$$
\mathsf{CertAccept}_\Gamma(h)=0\quad\text{or}\quad \mathsf{LearnAllowed}(h)=0.
$$

这就是 learning-freeze frontier。它不是重新证明 severe sensor attack safety，而是给 online learning update 加一个证书生命周期必要条件。

## 4. 修订后的贡献列表

候选贡献应写成：

1. **Model.** 定义 strategic-FDI setting 下 online-updated learning controller 的 certificate lifecycle，而不是只定义 sensor attack safety filter。
2. **Boundary.** 证明 sound certificate lifecycle 需要 update gate：非平凡更新后的 action map 必须保持在 $K_\Gamma(h)$ 内；当 kernel 为空时，certified learning 必须冻结或撤销。
3. **Unification.** 将已有 severe sensor attack safety filters、FT-CBF、secure estimation、robust MPC 解释为让 $K_\Gamma(h)$ 非空的正例；本工作补充 $K_\Gamma(h)$ 与 online update 之间的必要边界。
4. **Demo.** 展示三种机制：fixed severe-attack safety filter 安全但不学习；ungated learner 在 learning-aware FDI 下 unsafe；certificate-gated learner 在 kernel 非空时约束学习、kernel 为空时冻结。

## 5. 修改后的实验叙事

实验不应再说“我们提出 severe sensor attack safety filter”。应说：

| 机制 | 对照意义 | 预期结果 |
|---|---|---|
| Fixed severe-attack safety filter | 对应已有 positive control safety baseline | safe，但 learning update rate = 0 |
| Ungated online learner | 代表普通部署后学习控制器 | 在 learning-aware FDI 下可越界 |
| Certificate-gated learner | 本方向机制/边界演示 | kernel 非空时受限更新；kernel 为空时冻结 |
| Trusted-anchor variant | 命题 C 逃逸条件 | 收缩 $X_{\mathcal A}(h)$ 后恢复部分学习 |

核心图应是：

1. 横轴：状态歧义半径、攻击传感器数或 learning-aware poisoning strength。
2. 纵轴 1：certified kernel width。
3. 纵轴 2：learning update rate。
4. 纵轴 3：unsafe rate。

预期相变：攻击越强，kernel 越窄；当 kernel 为空，sound learner 的 update rate 必须为 0。

## 6. 论文叙事中的防撞表述

建议明确写：

> We do not claim that safety under sensor attacks is impossible. In fact, recent CBF-based severe-attack safety filters show that safety can be enforced when the plausible-state set admits a feasible safety kernel. Our result is orthogonal: once the controller is allowed to update online using the attacked history, certificate soundness imposes a gate on the update itself. If the update changes the action map outside the certified kernel, or if the kernel is empty, certified learning must be rejected or frozen.

中文：

> 我们不主张传感器攻击下安全控制不可能。相反，已有 CBF-based severe-attack safety filter 表明，只要 plausible-state set 上存在可行安全 kernel，固定控制器可以安全运行。本文补充的是在线更新维度：当控制器允许根据被攻击历史继续学习时，证书 soundness 会对更新本身施加门控；若更新后的 action map 离开 certified kernel，或 kernel 为空，certified learning 必须被拒绝或冻结。

## 7. 已同步修改的旧文档

已同步修改：

1. `stage3_toy_theorem.md`：强调 toy theorem 是 lifecycle gate 的最小反例，而不是 plausible-state safety filtering 新定理。
2. `stage3_certificate_extension.md`：加入 severe sensor attacks baseline 引用位置。
3. `stage3_certificate_gated_learner.md`：把 fixed severe-attack safety filter 作为 baseline，而 certificate-gated learner 是在线更新扩展。
4. 未来论文草稿：Related Work 中必须正面讨论 severe sensor attack safety filters。
