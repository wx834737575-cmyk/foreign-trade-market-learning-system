import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { MoneyTrendChart } from "./components/MoneyTrendChart";
import { TrendChart } from "./components/TrendChart";
import type { CalendarItem, ChannelItem, DashboardData, Indicator, NoteItem, SourceItem, Tone } from "./types";
import "./styles.css";

const navItems = [
  ["overview", "⌂", "首页总览"],
  ["domestic", "◫", "国内经济"],
  ["trade", "◎", "外贸环境"],
  ["fx", "↗", "汇率航运"],
  ["stocks", "▥", "股票市场"],
  ["business", "◇", "我的业务"],
  ["notes", "✎", "分析与笔记"],
  ["calendar", "□", "数据日历"],
  ["learning", "◉", "学习中心"],
  ["settings", "⚙", "系统设置"]
] as const;

const toneLabel: Record<Tone, string> = {
  positive: "良好",
  warning: "关注",
  negative: "谨慎",
  neutral: "待确认"
};

function formatValue(value: number, unit: string) {
  return `${value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}${unit}`;
}

function qualityLabel(status: string) {
  if (status === "verified") return "已核验";
  if (status === "demo_unverified") return "演示未核验";
  return "待核验";
}

export default function App() {
  const [active, setActive] = useState<(typeof navItems)[number][0]>("overview");
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [calendar, setCalendar] = useState<CalendarItem[]>([]);
  const [channels, setChannels] = useState<ChannelItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.dashboard(), api.sources(), api.calendar(), api.channels()])
      .then(([dashboardData, sourceData, calendarData, channelData]) => {
        setDashboard(dashboardData);
        setSources(sourceData);
        setCalendar(calendarData);
        setChannels(channelData);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const indicators = useMemo(() => {
    const map = new Map(dashboard?.indicators.map((item) => [item.code, item]));
    return {
      m1: map.get("CN_M1_YOY"),
      m2: map.get("CN_M2_YOY"),
      pmi: map.get("CN_MANUFACTURING_PMI"),
      m2Balance: map.get("CN_M2_BALANCE"),
      fx: map.get("CN_USDCNY_CENTRAL_PARITY"),
      scfi: map.get("SCFI_COMPOSITE"),
      ccfi: map.get("CCFI_COMPOSITE")
    };
  }, [dashboard]);

  if (error) {
    return <div className="fatal">系统暂时无法连接本地数据服务：{error}</div>;
  }
  if (!dashboard) return <div className="loading">正在加载本地决策系统…</div>;

  async function checkUpdates() {
    setUpdating(true);
    setUpdateMessage("正在逐项核验已接入的官方来源…");
    try {
      const result = await api.checkUpdates();
      const success = result.results.filter((item) => item.status === "success").length;
      setUpdateMessage(`检查完成：${success}/${result.results.length} 个官方来源正常`);
      const [dashboardData, sourceData] = await Promise.all([api.dashboard(), api.sources()]);
      setDashboard(dashboardData);
      setSources(sourceData);
    } catch (reason) {
      setUpdateMessage(reason instanceof Error ? reason.message : "检查更新失败");
    } finally {
      setUpdating(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <button className="menu-button" aria-label="菜单">☰</button>
          <div className="brand-mark">策</div>
          <div>
            <h1>外贸与投资决策系统</h1>
            <p>数据驱动决策 · 洞察创造价值</p>
          </div>
        </div>
        <div className="top-status">
          <div><span>数据状态：</span><strong className="status-pill">● {dashboard.dataStatus}</strong></div>
          <div><span>系统日期：</span><b>2026-07-20</b></div>
        </div>
        <div className="top-actions">
          <button className="ghost-button"><span className="badge">2</span> 更新提醒</button>
          <button className="primary-button" onClick={checkUpdates} disabled={updating}>{updating ? "核验中…" : "↻ 检查新数据"}</button>
          <button className="ghost-button">⚙ 系统设置</button>
        </div>
      </header>

      <aside className="sidebar">
        <nav>
          {navItems.map(([id, icon, label]) => (
            <button key={id} className={active === id ? "active" : ""} onClick={() => setActive(id)}>
              <span>{icon}</span>{label}
            </button>
          ))}
        </nav>
        <div className="sidebar-reminder">
          <h3>数据更新提醒</h3>
          <p><i className="dot green" />人民银行货币数据<br /><small>{indicators.m2 ? `${indicators.m2.period.slice(0, 7)} 已核验` : "等待官方数据"}</small></p>
          <p><i className="dot green" />国家统计局月度指标<br /><small>CPI、PPI、工业、社零已接入</small></p>
          <p><i className="dot amber" />海关出口数据<br /><small>待首份官方导出</small></p>
          <p><i className="dot green" />汇率与航运指数<br /><small>{indicators.fx ? "官方数据已接入" : "等待首次核验"}</small></p>
          <button onClick={() => setActive("calendar")}>查看完整日历 →</button>
        </div>
        <div className="profile"><div className="avatar">外</div><div><b>当前用户</b><small>外贸人 · 投资学习者</small></div></div>
      </aside>

      <main className="main-content">
        {updateMessage && <div className="update-message" role="status">{updateMessage}</div>}
        {active === "overview" && <Overview dashboard={dashboard} sources={sources} calendar={calendar} indicators={indicators} />}
        {active === "business" && <BusinessPage channels={channels} />}
        {active === "notes" && <NotesPage />}
        {active === "calendar" && <CalendarPage items={calendar} />}
        {active === "learning" && <LearningPage />}
        {!["overview", "business", "notes", "calendar", "learning"].includes(active) && <ModulePage active={active} sources={sources} />}
      </main>

      <footer className="footer">本系统用于个人经营分析和投资学习，不构成投资建议 · V0.3 核心月度指标版</footer>
    </div>
  );
}

function Overview({ dashboard, sources, calendar, indicators }: {
  dashboard: DashboardData;
  sources: SourceItem[];
  calendar: CalendarItem[];
  indicators: Record<string, Indicator | undefined>;
}) {
  const keyIndicators = dashboard.indicators.slice(0, 16);
  const pmiTrend = dashboard.trends.CN_MANUFACTURING_PMI ?? [];
  const m1Trend = dashboard.trends.CN_M1_YOY ?? [];
  const m2Trend = dashboard.trends.CN_M2_YOY ?? [];
  const fxTrend = dashboard.trends.CN_USDCNY_CENTRAL_PARITY ?? [];
  const pmiEvidence = sources.find((source) => source.code === "NBS")?.evidence;
  const pbocEvidence = sources.find((source) => source.code === "PBOC")?.evidence;
  const moneyVerified = indicators.m1?.qualityStatus === "verified" && indicators.m2?.qualityStatus === "verified";
  return (
    <>
      <div className="demo-banner"><b>混合质量保护已开启</b><span>只有明确标记“已核验”的指标可参与后续分析；演示或待核验数据仅用于界面布局。</span></div>
      <section className="section-card overview-section">
        <div className="section-heading"><div><h2>今日总览</h2><p>环境判断与数据质量分开显示，避免把待核验数据误当结论。</p></div><a href="#sources">查看判断规则 →</a></div>
        <div className="overview-grid">
          {dashboard.environment.map((item) => (
            <article className={`environment-card ${item.tone}`} key={item.name}>
              <span className="eyebrow">{item.name}</span>
              <strong>{item.status}</strong>
              <div className="rating"><span>●●●</span><em>●●</em><small>{toneLabel[item.tone]}</small></div>
              <p>{item.summary}</p>
            </article>
          ))}
          <article className="attention-card">
            <div><h3>今日重要提醒 <span>3</span></h3><ol><li>人民银行与国家统计局原始证据已保存</li><li>独立站上线前需要定义埋点</li><li>业务数据等待脱敏导出样本</li></ol></div>
            <button>查看数据日历 →</button>
          </article>
        </div>
      </section>

      <h2 className="block-title">核心数据看板</h2>
      <div className="dashboard-grid">
        <section className="section-card wide-card">
          <div className="card-title-row"><div><h3>货币供应量与剪刀差</h3><p>{moneyVerified ? "人民银行官方年度表 · XLSX主数据与HTML交叉核验" : "演示走势 · 正式版保留发布值与修订值"}</p></div><span className={moneyVerified ? "verified-tag" : "quality-tag"}>{moneyVerified ? "历史已核验" : "演示未核验"}</span></div>
          <div className="money-layout">
            {moneyVerified && m1Trend.length > 1 && m2Trend.length > 1 ? <MoneyTrendChart m1={m1Trend} m2={m2Trend} /> : moneyVerified ? <EmptyChart message="已取得当期值，历史同比序列仍在回填" height={190} /> : <TrendChart color="#2777f4" values={[8.6, 8.4, 8.2, 8.6, 8.6, 8]} labels={["1月", "2月", "3月", "4月", "5月", "6月"]} height={190} />}
            <div className="metric-stack">
              <MetricMini label="M2同比" value={indicators.m2 ? formatValue(indicators.m2.value, "%") : "—"} tone="blue" status={moneyVerified ? "已核验" : "演示数据"} />
              <MetricMini label="M1同比" value={indicators.m1 ? formatValue(indicators.m1.value, "%") : "—"} tone="green" status={moneyVerified ? "已核验" : "演示数据"} />
              <MetricMini label="剪刀差" value={dashboard.derived.m1M2Gap == null ? "—" : `${dashboard.derived.m1M2Gap}个百分点`} tone="amber" status={moneyVerified ? "由已核验值计算" : "演示数据"} />
            </div>
          </div>
          <CardFoot source="中国人民银行" update={pbocEvidence ? `证据 ${pbocEvidence.sha256.slice(0, 12)}…` : "来源链路建设中"} />
        </section>

        <section className="section-card compact-card">
          <div className="card-title-row"><div><h3>中国出口</h3><p>月度官方导出</p></div><span className="pending-tag">待首份导入</span></div>
          <div className="hero-number muted">—</div>
          <EmptyChart message="请从海关统计平台导出首份真实文件，完成格式适配后显示走势" />
          <CardFoot source="海关总署" update="官方文件链路已配置" />
        </section>

        <section className="section-card compact-card">
          <div className="card-title-row"><div><h3>汇率与航运</h3><p>USD/CNY中间价</p></div><span className={indicators.fx?.qualityStatus === "verified" ? "verified-tag" : "pending-tag"}>{indicators.fx?.qualityStatus === "verified" ? "已核验" : "待核验"}</span></div>
          <div className={indicators.fx ? "hero-number" : "hero-number muted"}>{indicators.fx ? indicators.fx.value.toFixed(4) : "—"}</div>
          {fxTrend.length > 1 ? <TrendChart color="#19a85b" values={fxTrend.map((item) => item.value)} labels={fxTrend.map((item) => item.period.slice(5))} /> : <EmptyChart message="等待中国货币网官方数据导入" />}
          <div className="shipping-inline"><span>SCFI <b>{indicators.scfi?.value.toFixed(2) ?? "—"}</b></span><span>CCFI <b>{indicators.ccfi?.value.toFixed(2) ?? "—"}</b></span><small>仅供本地个人学习</small></div>
          <CardFoot source="中国货币网 / 上海航运交易所" update={indicators.fx ? indicators.fx.period : "等待首次核验"} />
        </section>

        <section className="section-card sources-card" id="sources">
          <div className="card-title-row"><div><h3>数据来源</h3><p>官方核验入口</p></div></div>
          {sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" key={source.code}><span className="source-icon">{source.name[0]}</span><b>{source.name}</b><em>{source.evidence?.qualityStatus === "verified" ? "证据已保存" : source.acquisitionMode === "official_file_import" ? "官方文件导入" : source.acquisitionMode === "automatic_learning_only" ? "个人学习" : source.acquisitionMode === "manual_review" ? "人工核验" : "自动核验"}</em><i>{source.evidence ? `SHA ${source.evidence.sha256.slice(0, 8)} · ` : ""}进入官网</i></a>)}
        </section>

        <section className="section-card table-card">
          <div className="card-title-row"><div><h3>最新数据速览</h3><p>质量状态优先于数值展示</p></div></div>
          <div className="data-table">
            <div className="table-head"><span>指标名称</span><span>最新值</span><span>统计期</span><span>质量状态</span><span>来源</span></div>
            {keyIndicators.map((item) => <div className="table-row" key={item.code}><b>{item.name}</b><span>{formatValue(item.value, item.unit)}</span><span>{item.period.slice(0, 7)}</span><span><i className={`quality-dot ${item.qualityStatus}`} />{qualityLabel(item.qualityStatus)}</span><a href={item.source.url} target="_blank" rel="noreferrer">{item.source.name} ↗</a></div>)}
          </div>
        </section>

        <section className="section-card pmi-card">
          <div className="card-title-row"><div><h3>PMI走势</h3><p>制造业 · 官方原始证据已保存</p></div><span className="verified-tag">已核验</span></div>
          {pmiTrend.length > 0 ? <TrendChart color="#2777f4" values={pmiTrend.map((item) => item.value)} labels={pmiTrend.map((item) => `${Number(item.period.slice(5, 7))}月`)} height={180} /> : <EmptyChart message="等待国家统计局官方页面导入" />}
          <CardFoot source="国家统计局" update={pmiEvidence ? `证据 ${pmiEvidence.sha256.slice(0, 12)}…` : "等待原始证据"} />
        </section>

        <section className="section-card calendar-card">
          <div className="card-title-row"><div><h3>近期数据日历</h3><p>发布日期采用窗口，不写死</p></div></div>
          {calendar.map((item) => <div className="calendar-line" key={`${item.datasetCode}-${item.period}`}><span>{item.datasetCode}</span><b>{item.expectedFrom ?? "待确认"}</b><em>{item.status === "waiting" ? "等待发布" : "预计窗口"}</em></div>)}
        </section>
      </div>

      <div className="insight-grid">
        <Insight title="对我的外贸业务提示" items={["仅使用已核验宏观数据，经营规则仍需结合业务证据", "独立站埋点和UTM规范需在上线前完成", "三渠道统一按有效线索、报价和成交比较"]} />
        <Insight title="对股票学习的参考" items={["区分事实、规则信号与个人判断", "不从单月指标直接推导市场涨跌", "保存当时证据版本，支持事后复盘"]} />
        <Insight title="我的分析与判断" items={["记录观点、证据、信心等级和反例", "到期后补充业务结果与修订原因", "长期形成个人商业研究数据库"]} button="进入我的笔记 →" />
      </div>
    </>
  );
}

function MetricMini({ label, value, tone, status }: { label: string; value: string; tone: string; status: string }) {
  return <div className={`metric-mini ${tone}`}><span>{label}</span><strong>{value}</strong><small>{status}</small></div>;
}

function EmptyChart({ message, height }: { message: string; height?: number }) {
  return <div className="empty-chart" role="status" style={height ? { height } : undefined}><span>暂无可信趋势</span><small>{message}</small></div>;
}

function CardFoot({ source, update }: { source: string; update: string }) {
  return <div className="card-foot"><span>数据来源：{source}</span><span>{update}</span><button>查看详情 →</button></div>;
}

function Insight({ title, items, button }: { title: string; items: string[]; button?: string }) {
  return <section className="section-card insight-card"><h3>{title}</h3>{items.map((item) => <p key={item}><span>✓</span>{item}</p>)}{button && <button>{button}</button>}</section>;
}

function BusinessPage({ channels }: { channels: ChannelItem[] }) {
  return <div><div className="page-title"><h2>我的多渠道业务</h2><p>统一比较阿里巴巴国际站、中国制造网和独立站的线索质量与经营结果。</p></div><div className="channel-grid">{channels.map((channel) => <section className="section-card channel-card" key={channel.code}><span className={`channel-status ${channel.status}`}>{channel.status === "active" ? "运营中" : channel.status === "building" ? "建设中" : "计划中"}</span><h3>{channel.name}</h3><p>{channel.type === "owned_website" ? "自有渠道：访问 → 行为 → 询盘 → 成交" : "平台渠道：曝光 → 询盘 → 报价 → 成交"}</p><dl><div><dt>本月询盘</dt><dd>待导入</dd></div><div><dt>有效线索</dt><dd>待导入</dd></div><div><dt>成交</dt><dd>待导入</dd></div></dl>{channel.plannedLaunch && <small>计划上线：{channel.plannedLaunch}</small>}<button>配置数据导入 →</button></section>)}</div><section className="section-card tracking-plan"><h3>独立站上线前数据准备</h3><div className="check-grid"><p>✓ 统一UTM命名规则</p><p>✓ 表单字段和线索ID</p><p>✓ 产品与国家分类</p><p>✓ 邮件/WhatsApp点击事件</p><p>✓ 隐私同意记录</p><p>✓ 原始数据导出与备份</p></div></section></div>;
}

function NotesPage() {
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<NoteItem[]>([]);
  useEffect(() => { api.notes().then(setNotes).catch(() => setNotes([])); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    try {
      const created = await api.createNote({ period: String(form.get("period")), title: String(form.get("title")), content: String(form.get("content")), confidence: String(form.get("confidence")) });
      setNotes((current) => [created, ...current]);
      setSaved(true);
      formElement.reset();
    } finally { setBusy(false); }
  }
  return <div><div className="page-title"><h2>分析与笔记</h2><p>记录当时看到的证据、你的判断、信心程度和未来验证节点。</p></div><form className="section-card note-form" onSubmit={submit}><label>分析月份<input name="period" type="date" defaultValue="2026-07-01" required /></label><label>标题<input name="title" placeholder="例如：2026年7月外贸环境初步判断" required /></label><label>信心等级<select name="confidence" defaultValue="medium"><option value="low">较低</option><option value="medium">中等</option><option value="high">较高</option></select></label><label className="full">我的判断<textarea name="content" rows={10} placeholder="写下采用的数据、推理过程、可能的反例，以及对业务的影响。" required /></label><div className="form-actions"><p>{saved ? "已保存到本地数据库。" : "系统不会替你作最终决策。"}</p><button className="primary-button" disabled={busy}>{busy ? "保存中…" : "保存本月分析"}</button></div></form><section className="section-card note-history"><div className="card-title-row"><div><h3>历史分析记录</h3><p>按保存时间倒序，长期保留复盘依据</p></div><span className="verified-tag">{notes.length} 条</span></div>{notes.length === 0 ? <p className="empty-note">还没有分析记录。</p> : notes.map((note) => <article key={note.id}><div><h3>{note.title}</h3><small>{note.period} · 信心：{note.confidence === "high" ? "较高" : note.confidence === "low" ? "较低" : "中等"}</small></div><p>{note.content}</p></article>)}</section></div>;
}

function CalendarPage({ items }: { items: CalendarItem[] }) {
  return <div><div className="page-title"><h2>数据日历</h2><p>区分预计发布窗口、实际发布时间和抓取状态。</p></div><section className="section-card calendar-page">{items.map((item) => <article key={`${item.datasetCode}-${item.period}`}><div className="calendar-date"><b>{item.expectedFrom?.slice(8) ?? "?"}</b><span>{item.expectedFrom?.slice(0, 7) ?? "待确认"}</span></div><div><h3>{item.datasetCode}</h3><p>统计期：{item.period.slice(0, 7)} · 预计窗口：{item.expectedFrom ?? "待确认"} 至 {item.expectedTo ?? "待确认"}</p></div><span className="pending-tag">{item.status === "waiting" ? "等待发布" : "预计窗口"}</span></article>)}</section></div>;
}

function LearningPage() {
  const lessons = [{title:"同比和环比有什么区别？",body:"同比与上年同一时期比较，环比与紧邻上一时期比较。二者回答的问题不同。"},{title:"M1-M2剪刀差怎么计算？",body:"使用M1同比增速减去M2同比增速，结果单位是百分点，不是百分比。"},{title:"为什么单月数据不能直接下结论？",body:"春节、季末、半年末和基数效应都会造成波动，需要结合连续数据和其他指标。"},{title:"怎样把宏观数据用于外贸？",body:"把宏观指标作为环境证据，再与国家、产品、询盘和成交数据交叉验证。"}];
  return <div><div className="page-title"><h2>学习中心</h2><p>在使用过程中理解指标，而不是只接收系统结论。</p></div><div className="lesson-grid">{lessons.map((item, index) => <section className="section-card lesson-card" key={item.title}><span>0{index + 1}</span><h3>{item.title}</h3><p>{item.body}</p><button>查看完整说明 →</button></section>)}</div></div>;
}

function ModulePage({ active, sources }: { active: string; sources: SourceItem[] }) {
  const labels: Record<string, [string, string]> = {domestic:["国内经济","资金、价格与制造业景气模块"],trade:["外贸环境","出口、地区市场和海外需求模块"],fx:["汇率航运","报价利润与物流成本模块"],stocks:["股票市场","宏观与市场学习模块，不提供荐股"],settings:["系统设置","数据、备份、提醒和隐私设置"]};
  const [title, subtitle] = labels[active] ?? ["模块", "建设中"];
  return <div><div className="page-title"><h2>{title}</h2><p>{subtitle}</p></div><section className="section-card module-placeholder"><div className="placeholder-icon">⌁</div><h3>模块框架已经预留</h3><p>当前优先完成数据证据链和人民银行纵向样板。后续接入时不会改变页面和数据库核心结构。</p><div className="source-chips">{sources.map((source) => <span key={source.code}>{source.name}</span>)}</div></section></div>;
}
