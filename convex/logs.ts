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
    cursor: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 50;
    
    let query = ctx.db
      .query("logs")
      .withIndex("by_item_and_timestamp", (q) => q.eq("item_id", args.item_id))
      .order("desc");

    if (args.cursor) {
      query = query.filter((q) => q.lt(q.field("timestamp"), parseInt(args.cursor)));
    }

    const logs = await query.take(limit);
    
    return {
      logs,
      nextCursor: logs.length === limit ? logs[logs.length - 1].timestamp.toString() : null,
    };
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
