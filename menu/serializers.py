from rest_framework import serializers
from .models import Category, MenuItem, Table

class CategorySerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'p_name', 'slug', 'description', 'icon', 'is_active', 'order', 'items_count']    
    def get_items_count(self, obj):
        return obj.items.filter(is_active=True, is_available=True).count()


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'p_name', 'description', 'p_description',
                'ingredients', 'p_ingredients', 'price', 'image', 
                'category', 'category_name', 'is_available', 'is_active', 'is_popular']


class MenuItemDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'p_name', 'description', 'p_description',
                  'ingredients', 'p_ingredients', 'price', 'image', 
                  'category', 'category_name', 'is_available', 'is_active', 
                  'is_popular', 'created_at', 'updated_at']

class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ['id', 'table_number', 'qr_code', 'capacity', 'location', 'is_active']