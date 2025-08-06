import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import base64

def scatterplot_with_regression(df: pd.DataFrame, x: str, y: str) -> str:
    plt.figure(figsize=(8, 5))
    sns.scatterplot(data=df, x=x, y=y)
    sns.regplot(data=df, x=x, y=y, scatter=False, color='red', linestyle='dotted')

    plt.xlabel(x)
    plt.ylabel(y)
    plt.title(f"{x} vs {y} with Regression Line")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)

    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{image_base64}"
