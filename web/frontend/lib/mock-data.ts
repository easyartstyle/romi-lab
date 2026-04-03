export type MetricCard = {
  label: string;
  value: string;
};

export const previewMetrics: MetricCard[] = [
  { label: "Расход", value: "2 431 545" },
  { label: "Клики", value: "27 082" },
  { label: "Лиды", value: "825" },
  { label: "ROMI", value: "-51,02%" },
];

export const previewProjects = [
  { id: 1, name: "Тестовый проект", active: true },
  { id: 2, name: "Клиент Сова", active: false },
  { id: 3, name: "Март CRM", active: false },
];
