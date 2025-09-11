"use client";
import React from "react";

export type Project = { id: string; name: string };

const PROJECTS_KEY = 'requestor_projects_v1';
const ACTIVE_PROJECT_KEY = 'requestor_active_project_v1';

function uuid() { return Math.random().toString(36).slice(2, 10); }

function loadProjects(): { projects: Project[]; activeId: string } {
  if (typeof window === 'undefined') return { projects: [{ id: 'default', name: 'Default Project' }], activeId: 'default' };
  try {
    const stored = JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
    let projects: Project[] = Array.isArray(stored) && stored.length ? stored : [{ id: 'default', name: 'Default Project' }];
    // Deduplicate by id
    const byId = new Map<string, Project>();
    projects.forEach(p => { if (!byId.has(p.id)) byId.set(p.id, p); });
    projects = Array.from(byId.values());
    const activeId = String(localStorage.getItem(ACTIVE_PROJECT_KEY) || projects[0].id);
    return { projects, activeId };
  } catch {
    return { projects: [{ id: 'default', name: 'Default Project' }], activeId: 'default' };
  }
}

function saveProjects(projects: Project[], activeId: string) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
  localStorage.setItem(ACTIVE_PROJECT_KEY, activeId);
}

export const ProjectsContext = React.createContext<{
  projects: Project[];
  activeId: string;
  setActive: (id: string) => void;
  addProject: (name: string) => string; // returns created id
  removeProject: (id: string) => void;
  renameProject: (id: string, name: string) => void;
}>({ projects: [{ id: 'default', name: 'Default Project' }], activeId: 'default', setActive: () => {}, addProject: () => 'default', removeProject: () => {}, renameProject: () => {} });

export function ProjectsProvider({ children }: { children: React.ReactNode }) {
  const [{ projects, activeId }, setState] = React.useState(loadProjects());

  const persist = (nextProjects: Project[], nextActiveId: string) => {
    setState({ projects: nextProjects, activeId: nextActiveId });
    saveProjects(nextProjects, nextActiveId);
  };

  const setActive = (id: string) => { if (projects.some(p => p.id === id)) persist(projects, id); };
  const addProject = (name: string) => {
    const p: Project = { id: uuid(), name: name || `Project ${projects.length + 1}` };
    persist([...projects, p], p.id);
    return p.id;
  };
  const removeProject = (id: string) => {
    const filtered = projects.filter(p => p.id !== id);
    if (!filtered.length) return; // keep at least one
    const nextActive = (activeId === id) ? filtered[0].id : activeId;
    // Reassign rentals referencing this project to nextActive
    try {
      const RENTALS_KEY = 'requestor_rentals_v1';
      const raw = JSON.parse(localStorage.getItem(RENTALS_KEY) || '[]');
      if (Array.isArray(raw)) {
        const reassigned = raw.map((r: any) => (r && r.project_id === id) ? { ...r, project_id: nextActive } : r);
        localStorage.setItem(RENTALS_KEY, JSON.stringify(reassigned));
      }
    } catch {}
    persist(filtered, nextActive);
  };
  const renameProject = (id: string, name: string) => {
    const idx = projects.findIndex(p => p.id === id);
    if (idx >= 0) { const copy = projects.slice(); copy[idx] = { ...copy[idx], name }; persist(copy, activeId); }
  };

  return (
    <ProjectsContext.Provider value={{ projects, activeId, setActive, addProject, removeProject, renameProject }}>
      {children}
    </ProjectsContext.Provider>
  );
}

export function useProjects() { return React.useContext(ProjectsContext); }
