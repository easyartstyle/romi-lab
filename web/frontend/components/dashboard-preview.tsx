import { previewMetrics } from "@/lib/mock-data";

export function DashboardPreview() {
  return (
    <div className="content-preview">
      <h3>Веб-версия текущего отчета</h3>
      <div className="kpi-row">
        {previewMetrics.map((metric) => (
          <div className="metric-card" key={metric.label}>
            <div className="label">{metric.label}</div>
            <div className="value">{metric.value}</div>
          </div>
        ))}
      </div>
      <div className="filters-row">
        <div className="mini-input">Период: 01.02.2026 - 31.03.2026</div>
        <div className="mini-input">Источник: Все</div>
        <div className="mini-input">Тип: Все</div>
        <div className="mini-input">Кампания: Все</div>
      </div>
      <div className="mini-tabs">
        <div className="mini-tab active">Дата</div>
        <div className="mini-tab">Источник</div>
        <div className="mini-tab">Тип</div>
        <div className="mini-tab">Кампания</div>
        <div className="mini-tab">Группа</div>
        <div className="mini-tab">План</div>
      </div>
      <div className="table-preview">
        <div className="table-head-cell">Дата</div>
        <div className="table-head-cell">Расход</div>
        <div className="table-head-cell">Клики</div>
        <div className="table-head-cell">Лиды</div>
        <div className="table-head-cell">Продажи</div>
        <div className="table-head-cell">ROMI</div>

        <div className="table-cell">01.02.2026</div>
        <div className="table-cell">115 000</div>
        <div className="table-cell">1 900</div>
        <div className="table-cell">35</div>
        <div className="table-cell">1</div>
        <div className="table-cell">-40,87</div>

        <div className="table-cell">02.02.2026</div>
        <div className="table-cell">43 200</div>
        <div className="table-cell">1 800</div>
        <div className="table-cell">15</div>
        <div className="table-cell">0</div>
        <div className="table-cell">-100,00</div>

        <div className="table-cell total">ИТОГО</div>
        <div className="table-cell total">2 431 545</div>
        <div className="table-cell total">27 082</div>
        <div className="table-cell total">825</div>
        <div className="table-cell total">17</div>
        <div className="table-cell total">-51,02</div>
      </div>
    </div>
  );
}
