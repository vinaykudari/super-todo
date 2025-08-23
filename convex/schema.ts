import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  logs: defineTable({
    item_id: v.string(),
    message: v.string(),
    level: v.union(v.literal("info"), v.literal("warning"), v.literal("error"), v.literal("debug")),
    timestamp: v.number(),
    metadata: v.optional(v.any()),
  })
    .index("by_item_id", ["item_id"])
    .index("by_timestamp", ["timestamp"])
    .index("by_item_and_timestamp", ["item_id", "timestamp"]),
});
