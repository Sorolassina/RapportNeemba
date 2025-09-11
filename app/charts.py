import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def build_grouped_bars(df, outpath):
    x = range(len(df))
    plt.figure()
    plt.bar([i-0.2 for i in x], df["in"], width=0.4, label="In (%)")
    plt.bar([i+0.2 for i in x], df["out"], width=0.4, label="Out (%)")
    plt.xticks(list(x), df["stagiaire"], rotation=30, ha="right")
    plt.ylabel("Taux de réussite")
    plt.title("Taux de réussite In/Out")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()

def build_deltas(df, outpath):
    plt.figure()
    plt.bar(df["stagiaire"], df["delta"])
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Δ points")
    plt.title("Progression par participant")
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()
