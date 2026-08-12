from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BusinessChannel, Dataset, Observation, ReleaseCalendar, Source


def _ensure_source(
    db: Session,
    *,
    code: str,
    name: str,
    homepage_url: str,
    verification_url: str,
    acquisition_mode: str,
    notes: str,
) -> Source:
    source = db.scalar(select(Source).where(Source.code == code))
    if source is None:
        source = Source(code=code, name=name, homepage_url=homepage_url)
        db.add(source)
        db.flush()
    source.name = name
    source.homepage_url = homepage_url
    source.verification_url = verification_url
    source.acquisition_mode = acquisition_mode
    source.notes = notes
    return source


def _ensure_dataset(
    db: Session,
    *,
    source: Source,
    code: str,
    name: str,
    frequency: str,
    unit: str,
    methodology: str,
    expected_release_rule: str,
) -> Dataset:
    dataset = db.scalar(select(Dataset).where(Dataset.code == code))
    if dataset is None:
        dataset = Dataset(source_id=source.id, code=code, name=name, frequency=frequency, unit=unit)
        db.add(dataset)
    dataset.source_id = source.id
    dataset.name = name
    dataset.frequency = frequency
    dataset.unit = unit
    dataset.methodology = methodology
    dataset.expected_release_rule = expected_release_rule
    return dataset


def _ensure_new_reference_data(db: Session) -> None:
    nbs = _ensure_source(
        db,
        code="NBS",
        name="国家统计局",
        homepage_url="https://www.stats.gov.cn/",
        verification_url="https://www.stats.gov.cn/sj/zxfb/",
        acquisition_mode="automatic_with_review",
        notes="核心月度指标从官方数据发布目录自动发现并保存原始发布页；国家数据动态查询页仅作人工核验入口。",
    )
    cfets = _ensure_source(
        db,
        code="CFETS",
        name="中国外汇交易中心（中国货币网）",
        homepage_url="https://www.chinamoney.com.cn/",
        verification_url="https://www.chinamoney.com.cn/chinese/bkccpr/index.html?tab=2",
        acquisition_mode="automatic_with_review",
        notes="受权发布人民币汇率中间价；历史接口与当日官方JSON交叉核验并保存原始证据。",
    )
    sse = _ensure_source(
        db,
        code="SSE",
        name="上海航运交易所",
        homepage_url="https://www.sse.net.cn/",
        verification_url="https://www.sse.net.cn/index/singleIndex?indexType=scfi",
        acquisition_mode="automatic_learning_only",
        notes="仅保存SCFI、CCFI最新综合指数供本地个人学习；不批量抓取历史，不公开或商业发布。",
    )
    customs = _ensure_source(
        db,
        code="CUSTOMS",
        name="海关总署",
        homepage_url="https://www.customs.gov.cn/",
        verification_url="https://stats.customs.gov.cn/",
        acquisition_mode="official_file_import",
        notes="从海关统计数据在线查询平台人工导出官方文件；保存查询条件、原文件和SHA-256后再解析。等待首份真实导出样本完成格式适配。",
    )
    _ensure_dataset(
        db,
        source=nbs,
        code="CN_CPI_YOY",
        name="居民消费价格（CPI）同比",
        frequency="monthly",
        unit="%",
        methodology="国家统计局全国居民消费价格月度同比变动。",
        expected_release_rule="通常次月上旬发布，以国家统计局官方页面为准。",
    )
    _ensure_dataset(
        db,
        source=nbs,
        code="CN_CPI_MOM",
        name="居民消费价格（CPI）环比",
        frequency="monthly",
        unit="%",
        methodology="国家统计局全国居民消费价格月度环比变动。",
        expected_release_rule="通常次月上旬发布，以国家统计局官方页面为准。",
    )
    _ensure_dataset(
        db,
        source=nbs,
        code="CN_PPI_YOY",
        name="工业生产者出厂价格（PPI）同比",
        frequency="monthly",
        unit="%",
        methodology="国家统计局工业生产者出厂价格月度同比变动。",
        expected_release_rule="通常次月上旬发布，以国家统计局官方页面为准。",
    )
    _ensure_dataset(
        db,
        source=nbs,
        code="CN_PPI_MOM",
        name="工业生产者出厂价格（PPI）环比",
        frequency="monthly",
        unit="%",
        methodology="国家统计局工业生产者出厂价格月度环比变动。",
        expected_release_rule="通常次月上旬发布，以国家统计局官方页面为准。",
    )
    _ensure_dataset(
        db,
        source=nbs,
        code="CN_INDUSTRIAL_VALUE_ADDED_YOY",
        name="规模以上工业增加值同比",
        frequency="monthly",
        unit="%",
        methodology="国家统计局规模以上工业增加值月度实际同比增速。",
        expected_release_rule="通常次月中旬发布；1至2月可能合并发布。",
    )
    _ensure_dataset(
        db,
        source=nbs,
        code="CN_RETAIL_SALES_VALUE",
        name="社会消费品零售总额",
        frequency="monthly",
        unit="亿元",
        methodology="国家统计局社会消费品零售总额月度绝对量。",
        expected_release_rule="通常次月中旬发布；1至2月可能合并发布。",
    )
    _ensure_dataset(
        db,
        source=nbs,
        code="CN_RETAIL_SALES_YOY",
        name="社会消费品零售总额同比",
        frequency="monthly",
        unit="%",
        methodology="国家统计局社会消费品零售总额月度同比增速。",
        expected_release_rule="通常次月中旬发布；1至2月可能合并发布。",
    )
    _ensure_dataset(
        db,
        source=cfets,
        code="CN_USDCNY_CENTRAL_PARITY",
        name="USD/CNY中间价",
        frequency="daily",
        unit="人民币/美元",
        methodology="中国外汇交易中心受权发布的银行间外汇市场人民币汇率中间价。",
        expected_release_rule="中国货币网工作日上午公布；以官方页面实际时间为准。",
    )
    _ensure_dataset(
        db,
        source=sse,
        code="SCFI_COMPOSITE",
        name="上海出口集装箱运价综合指数（SCFI）",
        frequency="weekly",
        unit="点",
        methodology="上海航运交易所最新综合指数，仅供本地个人学习。",
        expected_release_rule="通常周五发布；节假日以官方页面为准。",
    )
    _ensure_dataset(
        db,
        source=sse,
        code="CCFI_COMPOSITE",
        name="中国出口集装箱运价综合指数（CCFI）",
        frequency="weekly",
        unit="点",
        methodology="上海航运交易所最新综合指数，仅供本地个人学习。",
        expected_release_rule="通常周五发布；节假日以官方页面为准。",
    )
    _ensure_dataset(
        db,
        source=customs,
        code="CN_CUSTOMS_EXPORT_VALUE_USD",
        name="中国出口金额",
        frequency="monthly",
        unit="亿美元",
        methodology="海关统计数据在线查询平台官方导出文件；查询口径随原文件一并留存。",
        expected_release_rule="月度发布，以海关总署官方平台实际更新为准。",
    )


def seed_database(db: Session) -> None:
    if db.scalar(select(Source.id).limit(1)) is not None:
        _ensure_new_reference_data(db)
        db.commit()
        return

    pboc = Source(
        code="PBOC",
        name="中国人民银行",
        homepage_url="https://www.pbc.gov.cn/",
        verification_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html",
        acquisition_mode="semi_automatic",
        notes="生产数据写入前必须完成当期官方入口和原始证据核验。",
    )
    nbs = Source(
        code="NBS",
        name="国家统计局",
        homepage_url="https://www.stats.gov.cn/",
        verification_url="https://www.stats.gov.cn/sj/",
        acquisition_mode="automatic_with_review",
    )
    customs = Source(
        code="CUSTOMS",
        name="海关总署",
        homepage_url="https://www.customs.gov.cn/",
        verification_url="https://www.customs.gov.cn/customs/302249/zfxxgk/2799825/302274/302277/index.html",
        acquisition_mode="manual_review",
    )
    db.add_all([pboc, nbs, customs])
    db.flush()

    _ensure_new_reference_data(db)

    datasets = [
        Dataset(source_id=pboc.id, code="CN_M0_BALANCE", name="M0余额", frequency="monthly", unit="亿元"),
        Dataset(source_id=pboc.id, code="CN_M1_BALANCE", name="M1余额", frequency="monthly", unit="亿元"),
        Dataset(source_id=pboc.id, code="CN_M2_BALANCE", name="M2余额", frequency="monthly", unit="亿元"),
        Dataset(source_id=pboc.id, code="CN_M1_YOY", name="M1同比", frequency="monthly", unit="%"),
        Dataset(source_id=pboc.id, code="CN_M2_YOY", name="M2同比", frequency="monthly", unit="%"),
        Dataset(source_id=nbs.id, code="CN_MANUFACTURING_PMI", name="制造业PMI", frequency="monthly", unit="%"),
    ]
    db.add_all(datasets)
    db.flush()

    by_code = {item.code: item for item in datasets}
    demo_values = {
        "CN_M0_BALANCE": Decimal("147400"),
        "CN_M1_BALANCE": Decimal("1184775.53"),
        "CN_M2_BALANCE": Decimal("3567108.43"),
        "CN_M1_YOY": Decimal("4.0"),
        "CN_M2_YOY": Decimal("8.0"),
        "CN_MANUFACTURING_PMI": Decimal("50.3"),
    }
    for code, value in demo_values.items():
        dataset = by_code[code]
        db.add(
            Observation(
                dataset_id=dataset.id,
                period=date(2026, 6, 1),
                value=value,
                unit=dataset.unit,
                published_at=datetime(2026, 7, 15, 9, 0),
                quality_status="demo_unverified",
                note="来自项目历史上下文或界面原型，仅用于布局，不得用于决策。",
            )
        )

    db.add_all(
        [
            BusinessChannel(code="ALIBABA", name="阿里巴巴国际站", channel_type="marketplace", lifecycle_status="active"),
            BusinessChannel(code="MADE_IN_CHINA", name="中国制造网", channel_type="marketplace", lifecycle_status="planned"),
            BusinessChannel(
                code="INDEPENDENT_SITE",
                name="独立站",
                channel_type="owned_website",
                lifecycle_status="building",
                planned_launch=date(2026, 12, 31),
                notes="上线前完成事件、UTM、表单、隐私同意和导出规范。",
            ),
        ]
    )
    db.add_all(
        [
            ReleaseCalendar(
                dataset_code="CN_MANUFACTURING_PMI",
                statistical_period=date(2026, 7, 1),
                expected_from=date(2026, 7, 31),
                expected_to=date(2026, 7, 31),
                status="waiting",
            ),
            ReleaseCalendar(
                dataset_code="CN_M2_BALANCE",
                statistical_period=date(2026, 7, 1),
                expected_from=date(2026, 8, 9),
                expected_to=date(2026, 8, 16),
                status="estimated_window",
            ),
        ]
    )
    db.commit()
