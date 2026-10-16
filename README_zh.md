# AXR ND2 Analyzer · 使用说明

用于 Nikon AXR **1–4 通道时间序列 ND2** 的半自动分析：自动寻找背景和响应 ROI，计算逐像素 ΔF/F₀，交互检查伪彩图和 traces，再导出定量结果。

## 安装与启动

1. 安装 [Python 3.12 或更高版本](https://www.python.org/downloads/windows/)，保留安装器中的 Tcl/Tk 组件。
2. 下载仓库 ZIP 并解压到可写入目录，或使用 Git 克隆仓库。
3. 首次使用双击 `Setup.bat`，自动创建 `.venv` 并安装依赖（需要网络）。
4. 之后双击 `Start.bat` 启动图形界面。

现有开发机器可直接使用已有环境。程序不修改原始 ND2；实验数据、结果、日志、虚拟环境及本机 Tcl 文件不包含在仓库中。

## 界面与基本操作

新版采用深蓝标题栏、青绿色主按钮和白色工作区。左侧分为文件区和三个设置标签页；右侧集中显示伪彩图、ROI 和 traces。处理期间显示进度条，窗口保持响应。

1. **Input & output**：Browse 选择 ND2。Results folder 默认设为 ND2 所在目录，也可另选。
2. **Analysis**：设置基线、平均响应范围、ROI 直径和背景参考通道。
3. 点击 **1. Load / recompute preview** 加载或重新计算。
4. 在右侧选择 Response ROI（白圈）或 Background ROI（青圈），按住圈内区域拖动。
5. **Display**：调整各通道色阶、色表及曲线颜色，点击 Apply display ranges / colors 刷新。
6. 检查图像和曲线后，点击 **2. Save reviewed results**。

窗口可缩放；标签页内容较长时可用滚轮或侧边滚动条。未使用通道的显示输入框会禁用。

## Analysis：时间范围与 ROI

### Baseline 与 Average

- Baseline 的两个框分别输入起始和结束值，用于生成基线图 F₀。
- Average 的两个框分别输入 a 和 b，用于生成响应平均图并自动寻找响应 ROI。
- 两组均可独立选择 **frames** 或 **seconds**，每框只填一个数值，不加方括号或逗号。
- frames 从 **1** 开始，含两个端点，仅接受整数。
- seconds 使用与 traces 相同的时间轴：ND2 时间戳减去首帧时间，以首帧为 **0 秒**。选择时间戳落在闭区间内的帧，不插值、不按平均帧率换算。
- 无帧落入范围、超出时间范围或无可用时间戳时会报错。若已知帧间隔，可在 Advanced 设置 Frame interval。
- 切换单位后会填入建议值，请核对后重新计算。`analysis.json → resolved_ranges` 保存实际使用的帧号。

默认 Baseline 为第 **2–7 帧**，Average 为第 **8–15 帧**；后者仅为初始示例，须按实际刺激时间修改。配置文件中仍用两元素数组表示范围，兼容旧配置。

### ROI 参数

| 参数 | 默认值与含义 |
| --- | --- |
| Background diameter | **50 µm 直径**，即半径 25 µm |
| Response diameter | **100 µm 直径**，即半径 50 µm |
| Background reference | Auto (last)，用最后一个通道寻找背景；也可选实际存在的 C1、C2 等 |
| Response ROI mode | independent：各通道独立搜索；shared：参考通道选定位置，所有通道共用 |
| Shared reference | shared 模式下用于自动寻找响应 ROI 的通道号 |

所有通道共用一个背景**位置**，但每个通道分别测量、扣除自己的逐帧背景强度。默认背景参考通道在 1/2/3/4 通道数据中依次为 C1/C2/C3/C4。

重新计算保留当前手动 ROI；若希望重新自动搜索，点击 **Reset automatic ROIs**。已有背景 ROI 时，单纯更换背景参考通道不会自动换位，需 Reset 后重新搜索。

### 拖动与跨文件复用

响应 ROI 拖动时，traces 即时更新；shared 模式下各通道响应 ROI 一起移动。背景 ROI 在所有图中同步移动，松开鼠标后重新计算背景、F₀ 和 ΔF/F₀。ROI 限制在视野内，图例显示有效像素比例。

比较药物处理前后时，勾选 **Keep ROIs for the next file / 保留 ROI**：

1. 在第一个文件中确定并检查 ROI，可先导出结果。
2. 保持勾选，Browse 第二个文件，再加载预览。
3. 程序沿用背景和各通道响应 ROI 的中心与直径，第二个文件独立计算自身的背景、F₀ 和 ΔF/F₀。

复用要求通道数、图像尺寸、像素标定和 ROI 直径一致；不一致会报错，不自动缩放。取消勾选后下一文件恢复自动选择，Reset 会清除保留位置。ROI 仅在当前会话内保留，关闭程序后不自动恢复。

相同坐标不等于组织未移动：程序不做配准，处理前后如有漂移需先配准或人工核对。还需核对两个文件的通道顺序是否一致。

## Display：各通道显示

每个通道可单独设置：

- Endpoint 1 / Endpoint 2：伪彩显示端点；可以从小到大，也可对调，但不能相等。
- 色表：jet、Fire、GreenFireBlue、mpl-viridis、mpl-plasma、inferno、magma、coolwarm、gray。
- Reverse：反转色表方向；对调端点也会反转，同时使用两者会相互抵消。
- Trace color：十六进制曲线颜色，支持直接编辑。

默认 C1–C4 曲线色依次为 `#008080`、`#EE8000`、`#E000E0`、`#800000`。

例如负向 off response 可设置端点 `-0.3` 和 `0`，再勾选 Reverse，使较强负向变化显示为暖色。显示设置不改变浮点数据或自动 ROI 搜索；自动 ROI 仍寻找**最大平均 ΔF/F₀**，负向响应区域请手动选择。

修改后点击 **Apply display ranges / colors**；预览、色条及保存的 RGB 图像采用相同映射。NaN 显示为黑色，色条数值保持从小到大。Fire 使用 ImageJ 控制色，GreenFireBlue 通过 cmap 的 ImageJ 集合提供。

## Advanced：处理与标定

| 参数 | 含义 |
| --- | --- |
| Initial Gaussian σ | 初始空间模糊，默认 1 像素，不混合通道或时间 |
| Display Gaussian σ | 第二次空间模糊，默认 1 像素，仅用于伪彩显示 |
| F₀ threshold min/max | 应用在背景扣除后的基线图 F₀ 上，默认 10 到 100000000 |
| Auto ROI valid fraction | 自动响应 ROI 至少包含的有效像素比例，默认 0.8 |
| Pixel size [x,y] | 默认 null 使用 ND2 标定；手动覆盖格式为 `[x_um,y_um]` |
| Frame interval | 默认 null 使用 ND2 时间戳；填写正数时用指定秒间隔生成时间轴 |

修改时间范围、直径、sigma、阈值或标定后需要重新计算才能保存。手动 ROI 可低于自动搜索的有效比例要求；完全没有有效像素时不能保存。

## 计算流程

1. 原始背景参考通道沿时间 T 平均，在整数像素中心搜索均值最低且完整位于视野内的物理圆形背景 ROI。支持 X/Y 像素大小不同。
2. 转为 float32，按通道和帧进行第一次空间 Gaussian blur，再扣除该帧该通道在背景 ROI 内的均值，避免无符号整数截断或负值丢失。
3. 选定基线帧平均得到 F₀。超出阈值范围或 F₀≤0 的像素置 NaN，同一通道全时间序列使用固定掩膜。
4. 逐像素计算 `(F(t) − F₀) / F₀`。保存未经显示模糊的 float32 数据。
5. 第二次 Gaussian blur 对有效像素归一化并保留原 NaN 掩膜，仅用于伪彩显示；Average 输出对应窗口的平均图。
6. 在未经第二次显示模糊的平均数值图中，寻找平均 ΔF/F₀ 最大的响应 ROI。
7. 主 trace 是 ROI 内有效像素的 `mean((F−F₀)/F₀)`，而不是先求 ROI 平均荧光再相除。单位为比值：0.3 表示 30%。

本任务中的“Z projection”实际指沿 **T 时间轴** 求平均。真实多 Z、多位置数据会被拒绝，需先选单层/单位置。没有可用时间戳且未指定帧间隔时，trace 用帧号，CSV 时间列留空。

自动最大响应 ROI 来自同一份数据，结果属于探索性最大响应；正式组间比较可复用独立确定的 ROI。程序未做漂白校正或运动校正。

## 输出文件

GUI 在 Results folder 下创建 `<ND2名称>_results_<时间戳>`，避免覆盖已有结果。C<n> 仅包含实际存在的通道；`<palette>` 替换为对应色表名。

| 文件 | 内容 |
| --- | --- |
| `C<n>_dff_float32.tif` | 定量 ΔF/F₀ 时间堆栈，含 NaN 和像素标定，可用 Fiji 打开 |
| `C<n>_dff_<palette>.tif` | 展示用 RGB 伪彩堆栈，不用于定量 |
| `C<n>_average_dff.tif` | 选定响应窗口的浮点平均图 |
| `C<n>_average_<palette>.bmp` | 对应的显示平均图 |
| `C<n>_F0.tif` | 应用阈值后的基线图 |
| `ROI_preview.png` | 平均强度、响应及 ROI 检查图 |
| `traces.png`、`traces.svg` | 曲线图 |
| `traces.csv` | 帧号、时间、各通道主 trace、各通道逐帧背景强度，共 `2+2×通道数` 列 |
| `analysis.json` | 来源、标定、时间、参数、实际帧范围、ROI 及有效比例 |
| `roi_masks.npz` | 背景与各通道响应 ROI 的布尔掩膜 |

`runs/` 保存 GUI 当次配置和日志。仅预览不会写入输入 ND2 目录；重新导出时根据当前 ROI 重算，以保持图像和 CSV 一致。

## 命令行与测试

```powershell
.\.venv\Scripts\python.exe analyze.py "D:\data\recording.nd2" --config settings.json --output "D:\analysis\recording_01"
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v
```

命令行不指定 output 时默认保存至 `<ND2目录>/results/<ND2名称>`，拒绝覆盖非空目录。默认测试使用合成数据，不依赖私人实验目录；设置环境变量 `AXR_TEST_ND2` 后可运行可选四通道实测数据测试。

## 常见问题

- **无法启动**：先运行 Setup.bat；确认 Python 版本及 Tcl/Tk 已安装。命令行运行 `python gui.py` 可查看错误。
- **未找到合适 ROI**：检查直径、像素标定、F₀ 阈值和有效比例；直径过大不会被自动缩小。
- **秒数范围无帧**：参照 traces 或 CSV 的实际时间戳，调整两个端点。
- **结果出现饱和颜色**：调整对应通道的显示端点，定量数据不受色阶裁剪影响。
- **换电脑**：只需源代码和 requirements.txt，在新电脑重新运行 Setup.bat，不要复制旧 `.venv`。

依赖及色表来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。`requirements-lock.txt` 记录已验证环境版本。
