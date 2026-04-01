/**
 * Xuzhi State Manager
 * 统一状态管理 - 学习 Claude Code 的 AppStateProvider 设计
 * 
 * 设计原则:
 * 1. 只读取，不修改 OpenClaw 状态
 * 2. 通过现有 API 获取数据
 * 3. 可独立禁用
 */

import { readFileSync, existsSync } from "fs";
import { join } from "path";

// ============================================================================
// Types
// ============================================================================

export interface XuzhiState {
  session: SessionState;
  memory: MemoryState;
  epoch: EpochState;
  rotation: RotationState;
  system: SystemState;
}

export interface SessionState {
  key: string;
  model: string;
  startTime: Date | null;
  messageCount: number;
}

export interface MemoryState {
  todayFile: string;
  exists: boolean;
  lines: number;
  chunks: number;
  files: number;
  lastSync: Date | null;
}

export interface EpochState {
  current: string;
  name: string;
  startDate: string;
  architect: string;
  status: string;
}

export interface RotationState {
  today: string;
  todayName: string;
  tomorrow: string;
  tomorrowName: string;
  weekday: number;
}

export interface SystemState {
  gateway: {
    running: boolean;
    url: string;
  };
  git: {
    xuzhiGenisis: GitStatus;
    xuzhiMemory: GitStatus;
    xuzhiWorkspace: GitStatus;
  };
  cron: {
    total: number;
    healthy: number;
  };
}

export interface GitStatus {
  branch: string;
  clean: boolean;
  ahead: number;
  behind: number;
}

// ============================================================================
// State Provider
// ============================================================================

export class XuzhiStateProvider {
  private home: string;
  private workspace: string;
  private genesisPath: string;
  private memoryPath: string;
  
  constructor() {
    this.home = process.env.HOME || "/root";
    this.workspace = join(this.home, ".openclaw", "workspace");
    this.genesisPath = join(this.home, "xuzhi_genesis");
    this.memoryPath = join(this.home, ".xuzhi_memory");
  }
  
  /**
   * 获取完整状态
   */
  getState(): XuzhiState {
    return {
      session: this.getSessionState(),
      memory: this.getMemoryState(),
      epoch: this.getEpochState(),
      rotation: this.getRotationState(),
      system: this.getSystemState(),
    };
  }
  
  /**
   * 获取会话状态
   */
  private getSessionState(): SessionState {
    // 从环境变量获取当前会话信息
    const sessionKey = process.env.OPENCLAW_SESSION_KEY || "agent:main:main";
    const model = process.env.OPENCLAW_MODEL || "default";
    
    return {
      key: sessionKey,
      model,
      startTime: null, // 需要从会话文件读取
      messageCount: 0, // 需要从会话文件读取
    };
  }
  
  /**
   * 获取记忆状态
   */
  private getMemoryState(): MemoryState {
    const today = new Date().toISOString().slice(0, 10);
    const todayFile = join(this.memoryPath, "memory", `${today}.md`);
    const exists = existsSync(todayFile);
    let lines = 0;
    
    if (exists) {
      try {
        const content = readFileSync(todayFile, "utf-8");
        lines = content.split("\n").length;
      } catch {
        lines = 0;
      }
    }
    
    // 从索引文件获取统计
    const indexPath = join(this.memoryPath, "index.json");
    let chunks = 0;
    let files = 0;
    
    if (existsSync(indexPath)) {
      try {
        const index = JSON.parse(readFileSync(indexPath, "utf-8"));
        chunks = index.chunk_count || 0;
        files = index.file_count || 0;
      } catch {
        // Ignore
      }
    }
    
    return {
      todayFile,
      exists,
      lines,
      chunks,
      files,
      lastSync: exists ? new Date() : null,
    };
  }
  
  /**
   * 获取纪元状态
   */
  private getEpochState(): EpochState {
    const epochPath = join(this.genesisPath, "public", "EPOCH_DEFINITIONS.md");
    
    // 默认值
    let epoch: EpochState = {
      current: "Xi",
      name: "Ξ 纪元",
      startDate: "2026-03-31",
      architect: "Ξ (Xi)",
      status: "EPOCH ASCENDING",
    };
    
    if (existsSync(epochPath)) {
      try {
        const content = readFileSync(epochPath, "utf-8");
        // 解析纪元信息
        const currentMatch = content.match(/\*\*当前纪元\*\*：(.+)/);
        if (currentMatch) {
          epoch.name = currentMatch[1].trim();
        }
      } catch {
        // Ignore
      }
    }
    
    return epoch;
  }
  
  /**
   * 获取轮值状态
   */
  private getRotationState(): RotationState {
    const agents: Record<string, string> = {
      "0": "PHI",    // 周日
      "1": "DELTA",  // 周一
      "2": "GAMMA",  // 周二
      "3": "THETA",  // 周三
      "4": "OMEGA",  // 周四
      "5": "PSI",    // 周五
      "6": "???",
    };
    
    const agentNames: Record<string, string> = {
      "PHI": "语言学/文学",
      "DELTA": "数学",
      "GAMMA": "自然科学",
      "THETA": "历史/社会科学",
      "OMEGA": "艺术",
      "PSI": "哲学",
    };
    
    const now = new Date();
    const weekday = now.getDay();
    const tomorrowWeekday = (weekday + 1) % 7;
    
    const today = agents[weekday.toString()] || "???";
    const tomorrow = agents[tomorrowWeekday.toString()] || "???";
    
    return {
      today,
      todayName: agentNames[today] || "未知",
      tomorrow,
      tomorrowName: agentNames[tomorrow] || "未知",
      weekday,
    };
  }
  
  /**
   * 获取系统状态
   */
  private getSystemState(): SystemState {
    // 简化版，实际需要调用 OpenClaw API
    return {
      gateway: {
        running: true,
        url: "127.0.0.1:18789",
      },
      git: {
        xuzhiGenisis: this.getGitStatus(this.genesisPath),
        xuzhiMemory: this.getGitStatus(this.memoryPath),
        xuzhiWorkspace: this.getGitStatus(join(this.home, "xuzhi_workspace")),
      },
      cron: {
        total: 7,
        healthy: 5,
      },
    };
  }
  
  /**
   * 获取 Git 状态
   */
  private getGitStatus(repoPath: string): GitStatus {
    if (!existsSync(join(repoPath, ".git"))) {
      return {
        branch: "N/A",
        clean: true,
        ahead: 0,
        behind: 0,
      };
    }
    
    // 简化版，实际需要执行 git 命令
    return {
      branch: "master",
      clean: true,
      ahead: 0,
      behind: 0,
    };
  }
}

// ============================================================================
// Singleton
// ============================================================================

let instance: XuzhiStateProvider | null = null;

export function getStateProvider(): XuzhiStateProvider {
  if (!instance) {
    instance = new XuzhiStateProvider();
  }
  return instance;
}

export function getXuzhiState(): XuzhiState {
  return getStateProvider().getState();
}
