"""Render the paired scores without implying that the three denominators are comparable."""
import argparse
import csv
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

def plot_sql_highlights(results, out):
    with (results / 'confirm-b-grades.csv').open(encoding='utf-8-sig', newline='') as source:
        grades = list(csv.DictReader(source))

    families = [('filter', 'Row filters'), ('date', 'Date conditions')]
    fig, axes = plt.subplots(1, 2, figsize=(9, 2.65), layout='constrained')
    background = '#f6f8fc'
    ink = '#182942'
    fig.patch.set_facecolor(background)
    for ax, (category, title) in zip(axes, families):
        rows = [row for row in grades if row['category'] == category]
        total = len(rows)
        if total == 0:
            raise ValueError(f'No grades for {category}')
        counts = [sum(row[key] == 'True' for row in rows) for key in ('base_pass', 'lora_pass')]
        ax.set_facecolor(background)
        ax.set_title(title, loc='left', color=ink, fontsize=14, fontweight='bold', pad=12)
        bars = ax.barh([1, 0], counts, height=.44, color=['#64758d', '#6244b7'], zorder=3)
        for bar, count in zip(bars, counts):
            ax.annotate(str(count), (count, bar.get_y() + bar.get_height()/2),
                        xytext=(5, 0), textcoords='offset points', va='center',
                        color=ink, fontsize=12, fontweight='bold')
        ax.set_yticks([1, 0], ['Raw Qwen', 'DataLens'])
        ax.set_xticks([total * i / 4 for i in range(5)])
        ax.set_xlim(0, total)
        ax.set_ylim(-.55, 1.55)
        ax.set_xlabel(f'Correct queries out of {total}', color=ink)
        ax.grid(axis='x', color='#dbe0eb', linewidth=.8)
        ax.tick_params(length=0, labelcolor=ink, pad=5)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.savefig(out, dpi=165)
    plt.close(fig)

def main():
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--sql-highlights', action='store_true', help='Plot the two SQL families featured in the project README.')
    a=p.parse_args()
    if a.sql_highlights:
        plot_sql_highlights(a.results, a.out)
        return
    files=['confirm-b-summary.json','spider-summary.json','business-summary.json']
    data=[json.loads((a.results/f).read_text(encoding='utf8')) for f in files]
    ceiling=min(1.0,math.ceil((max(r[m]/r['items'] for r in data for m in ('base','lora'))+.075)*10)/10)
    fig,axes=plt.subplots(1,3,figsize=(12.5,3.35),sharey=True,layout='constrained')
    fig.patch.set_facecolor('#f6f8fc')
    labels=[('Business SQL','All three fixtures match'),('Spider dev','Official test-suite accuracy'),('Business decisions','Both versions pass')]
    colors=['#566984','#6244b7']
    for ax,r,(title,metric) in zip(axes,data,labels):
        ax.set_facecolor('#f6f8fc')
        ax.set_title(title+'\n'+metric,fontsize=12,loc='left',color='#182942',linespacing=1.55)
        heights=[r[m]/r['items'] for m in ('base','lora')]
        bars=ax.bar([0,1],heights,color=colors,width=.48,zorder=3)
        for bar,m,h in zip(bars,('base','lora'),heights):
            ax.text(bar.get_x()+bar.get_width()/2,h+.008,f"{r[m]} / {r['items']}",ha='center',color='#182942',fontsize=11,fontweight='bold')
        ax.set_xlim(-.55,1.55);ax.set_ylim(0,ceiling);ax.set_yticks([i/10 for i in range(round(10*ceiling)+1)]);ax.yaxis.set_major_formatter(PercentFormatter(1,0))
        ax.set_xticks([0,1],['Raw Qwen','Final LoRA']);ax.grid(axis='y',color='#d8deea',lw=.8);ax.tick_params(length=0,labelcolor='#34455b')
        for sp in ax.spines.values():sp.set_visible(False)
    axes[0].set_ylabel('Pass rate',fontsize=10,color='#34455b')
    fig.savefig(a.out,dpi=165,bbox_inches='tight');plt.close(fig)
if __name__=='__main__':main()
