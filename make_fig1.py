"""Draws Figure 1 (where the tool-output check sits in the agent loop). Run: python make_fig1.py"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

fig, ax = plt.subplots(figsize=(9, 3.2))
ax.set_xlim(0, 10)
ax.set_ylim(0, 3.4)
ax.axis("off")

boxes = {
    "user": (0.1, 1.4, 1.3, 0.8, "User task\n(trusted)", "#E8EEF7"),
    "llm": (2.1, 1.4, 1.4, 0.8, "Agent LLM", "#E8EEF7"),
    "tool": (4.5, 1.4, 1.6, 0.8, "Tool\n(email, web, bank…)", "#F2F2F2"),
    "check": (7.2, 1.4, 1.4, 0.8, "Tool-output\ncheck", "#FBE3D6"),
    "attacker": (4.55, 2.6, 1.5, 0.6, "Attacker-written\ndata", "#F8D7DA"),
    "answer": (0.1, 0.1, 1.5, 0.6, "Final answer /\nactions", "#E2F0D9"),
}
for key, (x, y, w, h, label, color) in boxes.items():
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", fc=color, ec="#333", lw=1.2))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=9)


def arrow(p, q, text=None, rad=0.0, dy=0.12):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, lw=1.2, color="#333",
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, text, ha="center", fontsize=8, color="#444")


arrow((1.4, 1.8), (2.1, 1.8))
arrow((3.5, 1.8), (4.5, 1.8), "tool call", dy=0.1)
arrow((6.1, 1.8), (7.2, 1.8), "raw output", dy=0.1)
arrow((5.3, 2.6), (5.3, 2.2))
arrow((7.9, 1.4), (3.1, 1.4), rad=-0.3)
ax.text(5.5, 0.55, "checked output: pass / withhold / rewrite", ha="center", fontsize=8, color="#444")
arrow((2.4, 1.4), (1.2, 0.7))
ax.text(8.75, 1.8, "regex\nDeBERTa\nLLM detector\nLLM sanitizer", fontsize=7.5, va="center", color="#7a3b12")
fig.tight_layout()
fig.savefig("fig1_pipeline.png", dpi=200)
print("wrote fig1_pipeline.png")
