/**
 * Minimal IAIso skill loader (TypeScript / Node).
 *
 * Reads ./skills/<name>/SKILL.md files and exposes them as a
 * queryable registry. Zero runtime dependencies beyond Node's
 * built-in fs/path.
 *
 * Usage:
 *   import { SkillRegistry } from "./skills/loader/loader";
 *   const reg = await SkillRegistry.load("./skills");
 *   const skill = reg.get("iaiso-runtime-governed-agent");
 *   console.log(skill?.body);
 */

import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface Skill {
  name: string;
  description: string;
  version: string;
  tier: string;
  category: string;
  framework: string;
  license: string;
  body: string;
  metadata: Record<string, string>;
  path: string;
}

const FM_RE = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/;

function parseSkill(p: string, text: string): Skill {
  const m = text.match(FM_RE);
  if (!m) throw new Error(`${p}: missing or malformed frontmatter`);
  const [, fmText, body] = m;
  const meta: Record<string, string> = {};
  for (const line of fmText.split(/\n/)) {
    const idx = line.indexOf(":");
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim();
    let val = line.slice(idx + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    meta[key] = val;
  }
  const take = (k: string, fallback = ""): string => {
    const v = meta[k] ?? fallback;
    delete meta[k];
    return v;
  };
  return {
    name: take("name", path.basename(path.dirname(p))),
    description: take("description"),
    version: take("version"),
    tier: take("tier"),
    category: take("category"),
    framework: take("framework"),
    license: take("license"),
    body: body.replace(/^\n+/, ""),
    metadata: meta,
    path: p,
  };
}

export class SkillRegistry {
  private byName: Map<string, Skill>;

  constructor(skills: Skill[]) {
    this.byName = new Map(skills.map((s) => [s.name, s]));
  }

  static async load(root: string): Promise<SkillRegistry> {
    const skills: Skill[] = [];
    const entries = await fs.readdir(root, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const skillPath = path.join(root, entry.name, "SKILL.md");
      try {
        const text = await fs.readFile(skillPath, "utf-8");
        skills.push(parseSkill(skillPath, text));
      } catch (err: any) {
        if (err.code !== "ENOENT") {
          console.warn(`warn: failed to load ${skillPath}: ${err.message}`);
        }
      }
    }
    return new SkillRegistry(skills);
  }

  get(name: string): Skill | undefined { return this.byName.get(name); }
  has(name: string): boolean { return this.byName.has(name); }
  get size(): number { return this.byName.size; }

  *[Symbol.iterator](): IterableIterator<Skill> {
    yield* this.byName.values();
  }

  tier(t: string): Skill[] {
    return [...this].filter((s) => s.tier === t);
  }
  category(c: string): Skill[] {
    return [...this].filter((s) => s.category === c);
  }
  names(): string[] {
    return [...this.byName.keys()].sort();
  }
}
