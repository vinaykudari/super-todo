// convex/items.ts
import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

/**
 * Upsert on create or external edits.
 * Optional fields are only written when provided (not null).
 */
export const upsertItem = mutation({
  args: {
    item_id: v.string(),
    title: v.string(),
    description: v.optional(v.string()),
    state: v.union(v.literal("pending"), v.literal("processing"), v.literal("completed")),
    live_url: v.optional(v.string()),
    done_output: v.optional(v.any()),
    context: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("items")
      .withIndex("by_item_id", q => q.eq("item_id", args.item_id))
      .unique();

    const now = Date.now();

    const patch: Record<string, any> = {
      title: args.title,
      state: args.state,
      updated_at: now,
    };
    if (args.description !== undefined) patch.description = args.description;
    if (args.live_url !== undefined) patch.live_url = args.live_url;
    if (args.done_output !== undefined) patch.done_output = args.done_output;
    if (args.context !== undefined) patch.context = args.context;

    if (existing) {
      await ctx.db.patch(existing._id, patch);
      return existing._id;
    } else {
      const doc: Record<string, any> = {
        item_id: args.item_id,
        title: args.title,
        state: args.state,
        updated_at: now,
      };
      if (args.description !== undefined) doc.description = args.description;
      if (args.live_url !== undefined) doc.live_url = args.live_url;
      if (args.done_output !== undefined) doc.done_output = args.done_output;
      if (args.context !== undefined) doc.context = args.context;
      return await ctx.db.insert("items", doc);
    }
  },
});

/**
 * Set or update the Browser-Use live viewer URL (only when provided).
 */
export const setLiveUrl = mutation({
  args: { item_id: v.string(), live_url: v.optional(v.string()) },
  handler: async (ctx, { item_id, live_url }) => {
    const row = await ctx.db
      .query("items")
      .withIndex("by_item_id", q => q.eq("item_id", item_id))
      .unique();
    if (!row) return;

    const patch: Record<string, any> = { updated_at: Date.now() };
    if (live_url !== undefined) patch.live_url = live_url; // omit nulls
    await ctx.db.patch(row._id, patch);
  },
});

/**
 * Update status and optionally attach context/done_output.
 * Use this on completion to atomically record results.
 */
export const setStatus = mutation({
  args: {
    item_id: v.string(),
    state: v.union(v.literal("pending"), v.literal("processing"), v.literal("completed")),
    context: v.optional(v.any()),
    done_output: v.optional(v.any()),
  },
  handler: async (ctx, { item_id, state, context, done_output }) => {
    const row = await ctx.db
      .query("items")
      .withIndex("by_item_id", q => q.eq("item_id", item_id))
      .unique();
    if (!row) return;

    const patch: Record<string, any> = { state, updated_at: Date.now() };
    if (context !== undefined) patch.context = context;
    if (done_output !== undefined) patch.done_output = done_output;
    await ctx.db.patch(row._id, patch);
  },
});

/** Optional helper the UI can subscribe to */
export const getByItemId = query({
  args: { item_id: v.string() },
  handler: async (ctx, { item_id }) => {
    return await ctx.db
      .query("items")
      .withIndex("by_item_id", q => q.eq("item_id", item_id))
      .unique();
  },
});

export const listItems = query({
    args: {
      state: v.optional(
        v.union(v.literal("pending"), v.literal("processing"), v.literal("completed"))
      ),
      limit: v.optional(v.number()),
      cursor: v.optional(v.string()), // previous page's last updated_at as string
    },
    handler: async (ctx, args) => {
      const limit = args.limit ?? 50;
      const c = args.cursor ? parseInt(args.cursor, 10) : undefined;
  
      if (args.state) {
        // Filter by state + paginate by updated_at (desc)
        let q = ctx.db
          .query("items")
          .withIndex("by_state_updated_at", (x) => x.eq("state", args.state!))
          .order("desc");
        if (c !== undefined) q = q.filter((x) => x.lt(x.field("updated_at"), c));
        const items = await q.take(limit);
        return {
          items,
          nextCursor:
            items.length === limit ? String(items[items.length - 1].updated_at) : null,
        };
      }
  
      // No state filter
      let q = ctx.db.query("items").withIndex("by_updated_at").order("desc");
      if (c !== undefined) q = q.filter((x) => x.lt(x.field("updated_at"), c));
      const items = await q.take(limit);
      return {
        items,
        nextCursor:
          items.length === limit ? String(items[items.length - 1].updated_at) : null,
      };
    },
  });