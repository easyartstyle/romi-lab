"use client";

import type { ChangeEvent } from "react";
import { repairImportText, type ImportFieldDefinition } from "@/lib/import-mapping";

type ImportFileCardProps = {
  title: string;
  buttonLabel: string;
  fileName: string | null;
  rawRowCount: number;
  mappedRowCount: number;
  columns: string[];
  mapping: Record<string, string>;
  fields: ImportFieldDefinition[];
  previewRows: Record<string, unknown>[];
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onMappingChange: (fieldKey: string, columnName: string) => void;
};

export default function ImportFileCard({
  title,
  buttonLabel,
  fileName,
  rawRowCount,
  mappedRowCount,
  columns,
  mapping,
  fields,
  previewRows,
  onFileChange,
  onMappingChange,
}: ImportFileCardProps) {
  return (
    <div className="loader-file-card loader-file-card--rich">
      <div className="desktop-filter__label">{title}</div>
      <label className="file-picker-btn loader-action-btn">
        <span>{buttonLabel}</span>
        <input className="file-input-hidden" type="file" accept=".json,.csv,.xlsx,.xls" onChange={onFileChange} />
      </label>
      <div className="loader-file-name">{fileName ? `Файл: ${fileName}` : "Файл не выбран"}</div>
      <div className="loader-file-stats">
        <span>Прочитано: {rawRowCount}</span>
        <span>Распознано: {mappedRowCount}</span>
      </div>
      {columns.length ? (
        <>
          <div className="loader-section-caption">Сопоставление колонок</div>
          <div className="loader-mapping-grid">
            {fields.map((field) => (
              <label className="loader-mapping-field" key={field.key}>
                <span>
                  {field.label}
                  {field.required ? " *" : ""}
                </span>
                <select
                  className="desktop-select"
                  value={mapping[field.key] ?? ""}
                  onChange={(event) => onMappingChange(field.key, event.target.value)}
                >
                  <option value="">Не выбрано</option>
                  {columns.map((column) => (
                    <option key={column} value={column}>
                      {repairImportText(column)}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        </>
      ) : null}
      {previewRows.length ? (
        <div className="loader-preview-card">
          <div className="loader-section-caption">Предпросмотр первых строк</div>
          <div className="loader-preview-table-wrap">
            <table className="loader-preview-table">
              <thead>
                <tr>
                  {columns.slice(0, 8).map((column) => (
                    <th key={column}>{repairImportText(column)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewRows.map((row, index) => (
                  <tr key={index}>
                    {columns.slice(0, 8).map((column) => (
                      <td key={`${index}-${column}`}>{repairImportText(row[column] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
