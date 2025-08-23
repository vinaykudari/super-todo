import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  // ✅ existing
  logs: defineTable({
    item_id: v.string(),
    message: v.string(),
    level: v.union(
      v.literal("info"),
      v.literal("warning"),
      v.literal("error"),
      v.literal("debug")
    ),
    timestamp: v.number(),
    metadata: v.optional(v.any()),
  })
    .index("by_item_id", ["item_id"])
    .index("by_timestamp", ["timestamp"])
    .index("by_item_and_timestamp", ["item_id", "timestamp"]),

  // ✅ new
  items: defineTable({
    item_id: v.string(),
    title: v.string(),
    description: v.optional(v.string()),
    state: v.union(
      v.literal("pending"),
      v.literal("processing"),
      v.literal("completed")
    ),
    live_url: v.optional(v.string()),
    done_output: v.optional(v.any()),
    context: v.optional(v.any()),
    updated_at: v.number(),
  })
    .index("by_item_id", ["item_id"])
    .index("by_updated_at", ["updated_at"])
    .index("by_state", ["state"])
    .index("by_state_updated_at", ["state", "updated_at"]), // <- used by listItems
});
