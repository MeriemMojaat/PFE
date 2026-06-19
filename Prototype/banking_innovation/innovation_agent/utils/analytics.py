from django.db.models import Avg, Count, Q
from innovation_agent.models import Customer

def get_segment_stats(segment, quarter=None):
    qs = Customer.objects.filter(segment=segment)
    if quarter:
        qs = qs.filter(quarter=quarter)
    
    stats = qs.aggregate(
        avg_age=Avg('age'),
        avg_income=Avg('income'),
        avg_spending=Avg('monthly_spending'),
        avg_supermarket=Avg('supermarket_spending'),
        avg_online=Avg('online_shopping_score'),
        avg_mobile=Avg('mobile_payment_score'),
        avg_savings=Avg('savings_balance'),
        avg_tenure=Avg('tenure'),
        count=Count('id')
    )
    
    # Compute derived metrics
    total = stats['count'] or 1
    loan_pct = Customer.objects.filter(segment=segment, quarter=quarter, has_loan=True).count() / total * 100
    life_ins_pct = Customer.objects.filter(segment=segment, quarter=quarter, has_life_insurance=True).count() / total * 100
    health_ins_pct = Customer.objects.filter(segment=segment, quarter=quarter, has_health_insurance=True).count() / total * 100
    car_ins_pct = Customer.objects.filter(segment=segment, quarter=quarter, has_car_insurance=True).count() / total * 100
    home_ins_pct = Customer.objects.filter(segment=segment, quarter=quarter, has_home_insurance=True).count() / total * 100
    mobile_bank_pct = Customer.objects.filter(segment=segment, quarter=quarter, uses_mobile_banking=True).count() / total * 100
    online_bank_pct = Customer.objects.filter(segment=segment, quarter=quarter, uses_online_banking=True).count() / total * 100
    contactless_pct = Customer.objects.filter(segment=segment, quarter=quarter, uses_contactless=True).count() / total * 100
    credit_card_pct = Customer.objects.filter(segment=segment, quarter=quarter, has_credit_card=True).count() / total * 100
    
    # Average products held
    prod_counts = []
    for c in qs:
        if c.products_held:
            prod_counts.append(len(c.products_held.split(',')))
    avg_products = round(sum(prod_counts)/len(prod_counts), 1) if prod_counts else 0
    
    stats['loan_pct'] = round(loan_pct, 1)
    stats['life_ins_pct'] = round(life_ins_pct, 1)
    stats['health_ins_pct'] = round(health_ins_pct, 1)
    stats['car_ins_pct'] = round(car_ins_pct, 1)
    stats['home_ins_pct'] = round(home_ins_pct, 1)
    stats['mobile_bank_pct'] = round(mobile_bank_pct, 1)
    stats['online_bank_pct'] = round(online_bank_pct, 1)
    stats['contactless_pct'] = round(contactless_pct, 1)
    stats['credit_card_pct'] = round(credit_card_pct, 1)
    stats['avg_products_held'] = avg_products
    
    # Round all numeric values
    for key, value in stats.items():
        if isinstance(value, (int, float)) and key != 'count':
            stats[key] = round(value, 1)
    
    return stats

def detect_trends(segment):
    """Get QoQ changes between last two quarters."""
    quarters = Customer.objects.filter(segment=segment).values('quarter').distinct().order_by('quarter')
    q_list = list(quarters)
    if len(q_list) < 2:
        return {}, {}
    q1 = q_list[-2]['quarter']
    q2 = q_list[-1]['quarter']
    stats1 = get_segment_stats(segment, q1)
    stats2 = get_segment_stats(segment, q2)
    trends = {}
    metrics = ['avg_income', 'avg_spending', 'avg_savings', 'avg_online', 'avg_mobile']
    for m in metrics:
        old = stats1.get(m, 0)
        new = stats2.get(m, 0)
        if old and old != 0:
            trends[m] = round((new - old) / old * 100, 1)
        else:
            trends[m] = 0
    return trends, stats2

def get_trend_over_quarters(segment, metric='monthly_spending'):
    """Return data for trend chart."""
    quarters = Customer.objects.filter(segment=segment).values('quarter').distinct().order_by('quarter')
    data = []
    for q in quarters:
        qs = Customer.objects.filter(segment=segment, quarter=q['quarter'])
        val = qs.aggregate(avg=Avg(metric))['avg'] or 0
        data.append({'quarter': q['quarter'], 'value': round(val, 1)})
    return data

def get_product_adoption(segment):
    """Return percentage of customers holding each product."""
    customers = Customer.objects.filter(segment=segment)
    total = customers.count()
    if total == 0:
        return {}
    product_counts = {}
    for c in customers:
        if c.products_held:
            for p in c.products_held.split(','):
                p = p.strip()
                if p:
                    product_counts[p] = product_counts.get(p, 0) + 1
    return {p: round(count/total*100, 1) for p, count in product_counts.items()}    