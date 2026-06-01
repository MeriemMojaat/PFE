from django.contrib import admin
from .models import RecommendationFeedback, ProductScoreModifier

@admin.register(RecommendationFeedback)
class RecommendationFeedbackAdmin(admin.ModelAdmin):
    list_display = ('client_id', 'product_name', 'rating', 'comment_preview', 'created_at')
    list_filter = ('rating', 'created_at', 'product_name')
    search_fields = ('client_id', 'product_name', 'comment')
    date_hierarchy = 'created_at'
    readonly_fields = ('client_id', 'product_name', 'rating', 'comment', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('client_id', 'product_name', 'rating', 'comment', 'created_at')
        }),
    )

    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Commentaire'

@admin.register(ProductScoreModifier)
class ProductScoreModifierAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'modifier', 'last_updated')
    readonly_fields = ('product_name', 'modifier', 'last_updated')