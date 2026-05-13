"use client";
import React from "react";
import { useProjects } from "../../context/ProjectsContext";
import { Button } from "../../components/ui/Button";
import { FormField, TextInput } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { cn } from "../../components/ui/cn";

export default function ProjectsPage() {
  const { projects, activeId, setActive, addProject, removeProject, renameProject } = useProjects();

  return (
    <div className="space-y-4">
      <PageHeader
        title="Projects"
        actions={<Button onClick={() => addProject("")}>New Project</Button>}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {projects.map(p => (
          <div key={p.id} className={cn("card", p.id === activeId && "ring-2 ring-primary")}>
            <div className="card-body grid gap-3">
              <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-center">
                <FormField label="Name">
                  <TextInput value={p.name} onChange={(e) => renameProject(p.id, e.target.value)} />
                </FormField>
                <div className="flex gap-2 pt-6 sm:pt-0">
                  <Button variant="secondary" onClick={() => setActive(p.id)} disabled={activeId === p.id}>Set Active</Button>
                  <Button variant="danger" onClick={() => removeProject(p.id)} disabled={projects.length <= 1}>Delete</Button>
                </div>
              </div>
              <div className="text-xs text-text-secondary">ID: <span className="font-mono">{p.id}</span></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
