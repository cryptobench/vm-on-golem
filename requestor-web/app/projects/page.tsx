"use client";
import React from "react";
import { useProjects } from "../../context/ProjectsContext";

export default function ProjectsPage() {
  const { projects, activeId, setActive, addProject, removeProject, renameProject } = useProjects();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2>Projects</h2>
        <button className="btn btn-primary" onClick={() => addProject("")}>New Project</button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {projects.map(p => (
          <div key={p.id} className={"card " + (p.id === activeId ? 'ring-2 ring-brand-300' : '')}>
            <div className="card-body grid gap-3">
              <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-center">
                <div>
                  <label className="label">Name</label>
                  <input className="input" value={p.name} onChange={(e) => renameProject(p.id, e.target.value)} />
                </div>
                <div className="flex gap-2 pt-6 sm:pt-0">
                  <button className="btn btn-secondary" onClick={() => setActive(p.id)} disabled={activeId === p.id}>Set Active</button>
                  <button className="btn btn-danger" onClick={() => removeProject(p.id)} disabled={projects.length <= 1}>Delete</button>
                </div>
              </div>
              <div className="text-xs text-gray-600">ID: <span className="font-mono">{p.id}</span></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

