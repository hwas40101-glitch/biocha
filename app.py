
import pandas as pd
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
import os

TITLE_SIZE = 22
AXIS_TITLE_SIZE = 20
TICK_SIZE = 18
LEGEND_SIZE = 18
ABC_SIZE = 18

LEGEND_Y = -0.10

X_SHIFT = [-0.27, -0.09, 0.09, 0.27]
BAR_WIDTH = 0.18

ABC_Y_MANUAL = {
    "초장(㎝)": 17,
    "생장길이(㎝)": 5,
    "주경장(㎝)": 1.5,
    "분지수(개)": 1.5,
    "경경(mm)": 1,
    "엽장(㎝)": 1.5,
    "엽폭(㎝)": 0.8,
    "SPAD": 3.5,
    "착과수(개)": 0.2,
    "과고(mm)": 5,
    "과폭(mm)": 4
}

treatment_colors = {
    "무처리":"#E3F2F5",
    "200kg":"#FFF1D6",
    "500kg":"#EEE6FA",
    "1000kg":"#FBE4E4"
}

file_path = "data.xlsx"

variables = [
"초장(㎝)","생장길이(㎝)","주경장(㎝)","분지수(개)",
"경경(mm)","엽장(㎝)","엽폭(㎝)","SPAD",
"착과수(개)","과고(mm)","과폭(mm)"
]

treatment_order = ["무처리","200kg","500kg","1000kg"]

app = Dash(__name__)

app.layout = html.Div([
    html.H2("🌶 파프리카 생육조사 자동 모니터링"),
    dcc.Dropdown(
        id="variable",
        options=[{"label":i,"value":i} for i in variables],
        value=variables[0]
    ),
    dcc.Graph(id="graph")
])

def tukey_to_letters(df, var):
    tukey = pairwise_tukeyhsd(endog=df[var], groups=df["처리"], alpha=0.05)
    result = pd.DataFrame(data=tukey._results_table.data[1:], columns=tukey._results_table.data[0])

    means = df.groupby("처리")[var].mean().sort_values(ascending=False)

    letters = "abcdefghijklmnopqrstuvwxyz"
    group_letter = {g:"" for g in means.index}
    assigned = []

    for g in means.index:
        for letter in letters:
            conflict = False
            for other in assigned:
                if letter in group_letter[other]:
                    row = result[
                        ((result["group1"]==g)&(result["group2"]==other)) |
                        ((result["group1"]==other)&(result["group2"]==g))
                    ]
                    if not row.empty and row["reject"].values[0]:
                        conflict = True
                        break
            if not conflict:
                group_letter[g] += letter
                break
        assigned.append(g)

    return group_letter

@app.callback(
    Output("graph","figure"),
    Input("variable","value")
)
def update_graph(var):

    df = pd.read_excel(file_path)

    df["조사일"] = pd.to_datetime(df["조사일"])
    df = df.dropna(subset=["조사일"])

    df["처리"] = df["처리"].astype(str).str.replace(",","").str.strip()
    df["처리"] = df["처리"].replace({
        "1000":"1000kg","200":"200kg","500":"500kg"
    })

    df = df[df[var].notna()]

    plant_mean = df.groupby(["조사일","처리","반복","주반복"], as_index=False)[var].mean()
    rep_mean = plant_mean.groupby(["조사일","처리","반복"], as_index=False)[var].mean()

    trt_mean = rep_mean.groupby(["조사일","처리"], as_index=False)[var].mean()
    trt_se = rep_mean.groupby(["조사일","처리"], as_index=False)[var].sem()

    trt_mean["SE"] = trt_se[var]
    trt_mean["month"] = trt_mean["조사일"].dt.month

    months = sorted(trt_mean["month"].unique())

    fig = go.Figure()

    for i, t in enumerate(treatment_order):
        sub = trt_mean[trt_mean["처리"]==t]
        if sub.empty:
            continue

        x = sub["month"].map(lambda m: months.index(m))

        fig.add_trace(go.Bar(
            x=x + X_SHIFT[i],
            y=sub[var],
            name=t,
            width=BAR_WIDTH,
            marker=dict(color=treatment_colors[t], line=dict(color="black", width=1)),
            error_y=dict(type="data", array=sub["SE"])
        ))

    y_max = 0

    for date in rep_mean["조사일"].unique():
        sub = rep_mean[rep_mean["조사일"]==date]

        if sub["처리"].nunique() < 2:
            continue

        group_letter = tukey_to_letters(sub, var)

        month = pd.to_datetime(date).month
        base_x = months.index(month)

        means = sub.groupby("처리")[var].mean()
        se = sub.groupby("처리")[var].sem()

        for i, t in enumerate(treatment_order):
            if t not in group_letter:
                continue

            offset = ABC_Y_MANUAL.get(var, 1)
            y_val = means[t] + se[t] + offset

            if y_val > y_max:
                y_max = y_val

            fig.add_annotation(
                x=base_x + X_SHIFT[i],
                y=y_val,
                text=group_letter[t],
                showarrow=False,
                font=dict(size=ABC_SIZE)
            )

    fig.update_xaxes(
        tickvals=list(range(len(months))),
        ticktext=[f"{m}월" for m in months],
        tickfont=dict(size=TICK_SIZE),
        range=[-0.5, len(months)-0.5]
    )

    fig.update_yaxes(
        range=[0, y_max * 1.1],
        showgrid=True,
        gridcolor="lightgray",
        griddash="dot"
    )

    fig.add_shape(
        type="rect",
        xref="x",
        yref="y",
        x0=-0.5,
        x1=len(months)-0.5,
        y0=0,
        y1=y_max * 1.1,
        line=dict(color="black", width=1.5)
    )

    fig.update_layout(
        title=dict(text=var, font=dict(size=TITLE_SIZE)),
        plot_bgcolor="white",
        margin=dict(l=40, r=40, t=60, b=60),
        xaxis_title="",
        yaxis=dict(
            title=dict(text=var, font=dict(size=AXIS_TITLE_SIZE)),
            tickfont=dict(size=TICK_SIZE)
        ),
        legend=dict(
            orientation="h",
            y=LEGEND_Y,
            x=0.5,
            xanchor="center",
            font=dict(size=LEGEND_SIZE)
        ),
        barmode="group"
    )

    return fig


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8050)))
