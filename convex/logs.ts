import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

// Add a new log entry
export const addLog = mutation({
  args: {
    item_id: v.string(),
    message: v.string(),
    level: v.union(v.literal("info"), v.literal("warning"), v.literal("error"), v.literal("debug")),
    metadata: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const logId = await ctx.db.insert("logs", {
      item_id: args.item_id,
      message: args.message,
      level: args.level,
      timestamp: Date.now(),
      metadata: args.metadata,
    });
    return logId;
  },
});

// Get logs for a specific item (with pagination)
export const getLogsByItemId = query({
  args: {
    item_id: v.string(),
    limit: v.optional(v.number()),
    cursor: v.optional(v.string()),      // stringified millis
    direction: v.optional(v.union(v.literal("asc"), v.literal("desc"))),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 50;
    const dir = args.direction ?? "desc";
    const c = args.cursor ? parseInt(args.cursor, 10) : undefined;

    let q = ctx.db
      .query("logs")
      .withIndex("by_item_and_timestamp", (x) => x.eq("item_id", args.item_id));

    if (dir === "desc") {
      q = q.order("desc");
      if (c !== undefined) q = q.filter((x) => x.lt(x.field("timestamp"), c));
      const logs = await q.take(limit);
      return {
        logs,
        nextCursor:
          logs.length === limit ? String(logs[logs.length - 1].timestamp) : null,
      };
    } else {
      // asc
      q = q.order("asc");
      if (c !== undefined) q = q.filter((x) => x.gt(x.field("timestamp"), c));
      const logs = await q.take(limit);
      return {
        logs,
        nextCursor:
          logs.length === limit ? String(logs[logs.length - 1].timestamp) : null,
      };
    }
  },
});

// Get recent logs across all items (for admin/monitoring)
export const getRecentLogs = query({
  args: {
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 100;
    
    const logs = await ctx.db
      .query("logs")
      .withIndex("by_timestamp")
      .order("desc")
      .take(limit);
    
    return logs;
  },
});

// Stream logs for a specific item (real-time subscription)
export const streamLogsByItemId = query({
  args: {
    item_id: v.string(),
    since: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const since = args.since ?? 0;
    
    const logs = await ctx.db
      .query("logs")
      .withIndex("by_item_and_timestamp", (q) => 
        q.eq("item_id", args.item_id).gt("timestamp", since)
      )
      .order("asc")
      .collect();
    
    return logs;
  },
});
