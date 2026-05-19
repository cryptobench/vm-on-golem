"use client";
import React from "react";
import { RiArrowDownSLine, RiFolderLine } from "@remixicon/react";
import { useProjects } from "../../context/ProjectsContext";
import { Input, Modal } from "@golem/ui";
import { cn } from "@golem/ui";

export function ProjectSwitcher({ className }: { className?: string }) {
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

  React.useEffect(() => {
    const openSwitcher = () => setOpen(true);
    const openNewProject = () => setShowNew(true);
    window.addEventListener("requestor-open-project-switcher", openSwitcher);
    window.addEventListener("requestor-open-new-project", openNewProject);
    return () => {
      window.removeEventListener("requestor-open-project-switcher", openSwitcher);
      window.removeEventListener("requestor-open-new-project", openNewProject);
    };
  }, []);

  const active = projects.find(p => p.id === activeId) || projects[0];
  const hasSelectedProject = !!active && !(active.id === "default" && active.name === "Default Project");

  const createProject = () => {
    const trimmed = name.trim();
    const id = addProject(trimmed);
    setActive(id);
    setShowNew(false);
    setName("");
  };

  return (
    <div className={cn("relative w-full sm:max-w-md", className)} ref={ref}>
      <div className="relative">
        <button
          className="inline-flex h-14 w-full items-center justify-between rounded-lg border border-border bg-surface px-5 text-left shadow-sm transition hover:bg-surface-muted"
          onClick={() => setOpen(o => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className="min-w-0">
            <span className="block text-xs text-text-muted">Active project</span>
            <span className="mt-1 flex min-w-0 items-center gap-2 text-sm font-medium text-text-primary">
              <RiFolderLine className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden />
              <span className="truncate">{hasSelectedProject ? active.name : "No project selected"}</span>
            </span>
          </span>
          <RiArrowDownSLine className="ml-3 h-5 w-5 shrink-0 text-text-secondary" aria-hidden />
        </button>
        {open && (
          <div className="absolute z-20 mt-2 w-full rounded-lg border border-border bg-surface shadow-popover">
            <ul role="listbox" className="max-h-60 overflow-auto py-1 text-sm">
              {projects.map(p => (
                <li
                  key={p.id}
                  role="option"
                  aria-selected={activeId === p.id}
                  className={"flex cursor-pointer items-center justify-between px-3 py-2 hover:bg-surface-muted " + (activeId === p.id ? 'bg-surface-muted' : '')}
                  onClick={() => { setActive(p.id); setOpen(false); }}
                >
                  <span className="truncate">{p.id === "default" && p.name === "Default Project" ? "No project selected" : p.name}</span>
                  {activeId === p.id && <span className="text-xs text-primary">Selected</span>}
                </li>
              ))}
              <li className="my-1 border-t border-border" />
              <li
                role="option"
                className="cursor-pointer px-3 py-2 text-primary hover:bg-primary-soft"
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
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="My Project" />
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
