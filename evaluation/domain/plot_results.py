"""Render the paired scores without implying that the three denominators are comparable."""
import argparse
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

def main():
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('out',type=Path);a=p.parse_args()
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
