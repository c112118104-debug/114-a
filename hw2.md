import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd

# 任務表格資料
tasks = {
    1: {"name": "研擬計畫", "duration": 1, "predecessors": []},
    2: {"name": "任務分配", "duration": 4, "predecessors": [1]},
    3: {"name": "取得硬體", "duration": 17, "predecessors": [1]},
    4: {"name": "程式開發", "duration": 70, "predecessors": [2]},
    5: {"name": "安裝硬體", "duration": 10, "predecessors": [3]},
    6: {"name": "程式測試", "duration": 30, "predecessors": [4]},
    7: {"name": "撰寫使用手冊", "duration": 25, "predecessors": [5]},
    8: {"name": "轉換檔案", "duration": 20, "predecessors": [5]},
    9: {"name": "系統測試", "duration": 25, "predecessors": [6]},
    10: {"name": "使用者訓練", "duration": 20, "predecessors": [7, 8]},
    11: {"name": "使用者測試", "duration": 25, "predecessors": [9, 10]},
}

# 建立有向圖
G = nx.DiGraph()
for task_id, task in tasks.items():
    G.add_node(task_id, duration=task["duration"], name=task["name"])
    for pred in task["predecessors"]:
        G.add_edge(pred, task_id)

# 計算最早開始與最早完成時間 (Forward Pass)
ES, EF = {}, {}
for node in nx.topological_sort(G):
    if not list(G.predecessors(node)):
        ES[node] = 0
    else:
        ES[node] = max(EF[pred] for pred in G.predecessors(node))
    EF[node] = ES[node] + G.nodes[node]["duration"]

# 計算最晚開始與最晚完成時間 (Backward Pass)
LS, LF = {}, {}
max_EF = max(EF.values())
for node in reversed(list(nx.topological_sort(G))):
    if not list(G.successors(node)):
        LF[node] = max_EF
    else:
        LF[node] = min(LS[succ] for succ in G.successors(node))
    LS[node] = LF[node] - G.nodes[node]["duration"]

# 計算浮時與關鍵路徑
slack = {node: LS[node] - ES[node] for node in G.nodes()}
critical_path = [node for node in G.nodes() if slack[node] == 0]

print("最早開始時間 (ES):", ES)
print("最早完成時間 (EF):", EF)
print("最晚開始時間 (LS):", LS)
print("最晚完成時間 (LFhw2.md):", LF)
print("關鍵路徑:", " → ".join(tasks[n]["name"] for n in critical_path))

# 畫 PERT/CPM 圖
pos = nx.spring_layout(G)
labels = {n: f"{n}.{tasks[n]['name']}\n({tasks[n]['duration']}天)" for n in G.nodes()}
nx.draw(G, pos, with_labels=True, labels=labels, node_size=3000, node_color="lightblue", arrowsize=20)
plt.title("PERT/CPM 圖")
plt.show()

# 畫甘特圖
df = pd.DataFrame([
    dict(Task=f"{i}.{tasks[i]['name']}", 
         Start=ES[i], 
         Finish=EF[i]) for i in tasks
])

fig, ax = plt.subplots(figsize=(10,6))
for i, row in enumerate(df.itertuples()):
    ax.barh(i, row.Finish-row.Start, left=row.Start, color="skyblue")
    ax.text(row.Start, i, f"{row.Task}", va="center", ha="right")

ax.set_yticks(range(len(df)))
ax.set_yticklabels(df["Task"])
ax.set_xlabel("時間 (天)")
plt.title("專案甘特圖")
plt.show()
