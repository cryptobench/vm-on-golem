"use client";
import React from "react";
import { useProjects } from "../../context/ProjectsContext";
import { Modal } from "../ui/Modal";

export function ProjectSwitcher() {
  const { projects, activeId, setActive, addProject } = useProjects();
  const [open, setOpen] = React.useState(false);
  const [showNew, setShowNew] = React.useState(false);
  const [name, setName] = React.useState("");
  const ref = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const active = projects.find(p => p.id === activeId) || projects[0];

  const createProject = () => {
    const trimmed = name.trim();
    const id = addProject(trimmed);
    setActive(id);
    setShowNew(false);
    setName("");
  };

  return (
    <div className="px-4 py-4 border-b" ref={ref}>
      <div className="label mb-1">Project</div>
      <div className="relative">
        <button
          className="w-full inline-flex items-center justify-between rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm hover:bg-gray-50"
          onClick={() => setOpen(o => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className="truncate text-left">{active?.name}</span>
          <svg className="ml-2 h-4 w-4 text-gray-500" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
            <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.25 8.29a.75.75 0 01-.02-1.08z" clipRule="evenodd" />
          </svg>
        </button>
        {open && (
          <div className="absolute z-20 mt-2 w-full rounded-md border border-gray-200 bg-white shadow-lg">
            <ul role="listbox" className="max-h-60 overflow-auto py-1 text-sm">
              {projects.map(p => (
                <li
                  key={p.id}
                  role="option"
                  aria-selected={activeId === p.id}
                  className={"flex cursor-pointer items-center justify-between px-3 py-2 hover:bg-gray-50 " + (activeId === p.id ? 'bg-gray-50' : '')}
                  onClick={() => { setActive(p.id); setOpen(false); }}
                >
                  <span className="truncate">{p.name}</span>
                  {activeId === p.id && <span className="text-xs text-brand-600">Selected</span>}
                </li>
              ))}
              <li className="my-1 border-t" />
              <li
                role="option"
                className="cursor-pointer px-3 py-2 text-brand-700 hover:bg-brand-50"
                onClick={() => { setOpen(false); setShowNew(true); }}
              >
                Create new project…
              </li>
            </ul>
          </div>
        )}
      </div>

      <Modal open={showNew} onClose={() => setShowNew(false)}>
        <div className="card-body">
          <div className="text-lg font-semibold">New Project</div>
          <div className="mt-3">
            <label className="label">Name</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="My Project" />
          </div>
          <div className="mt-4 flex items-center justify-end gap-2">
            <button className="btn btn-secondary" onClick={() => setShowNew(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={createProject} disabled={!name.trim().length}>Create</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
