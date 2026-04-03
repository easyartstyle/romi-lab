import { previewProjects } from "@/lib/mock-data";

export function SidebarPreview() {
  return (
    <div className="sidebar-preview">
      <h3>Проекты</h3>
      <div className="mini-list">
        {previewProjects.map((project) => (
          <div className="project-chip" key={project.id}>
            {project.name}
          </div>
        ))}
      </div>
      <div className="actions-row">
        <button className="primary-btn">Загрузить</button>
        <button className="secondary-btn">Новый</button>
      </div>
    </div>
  );
}
