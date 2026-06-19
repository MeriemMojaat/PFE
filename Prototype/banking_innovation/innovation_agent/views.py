from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.db import models
from io import BytesIO
import datetime
import os
import re

# ReportLab imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from innovation_agent.utils.synthetic_data import generate_synthetic_customers
from innovation_agent.utils.analytics import get_segment_stats, detect_trends, get_trend_over_quarters, get_product_adoption
from innovation_agent.utils.llm_agent import generate_innovation_recommendation
from innovation_agent.models import Customer

# Try to register a nice font, fallback to Helvetica if not available
try:
    pdfmetrics.registerFont(TTFont('Inter', 'Inter-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Inter-Bold', 'Inter-Bold.ttf'))
    FONT_NAME = 'Inter'
    FONT_BOLD = 'Inter-Bold'
except:
    FONT_NAME = 'Helvetica'
    FONT_BOLD = 'Helvetica-Bold'

# --- Helper to convert ** to proper bold tags ---
def format_bold(text: str) -> str:
    """
    Convert **bold** markers to <b>bold</b> tags for ReportLab.
    Handles multiple pairs correctly.
    """
    if not text:
        return text
    # Replace ** with <b> and </b> alternating
    parts = text.split('**')
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            result.append(part)
        else:
            result.append(f"<b>{part}</b>")
    return ''.join(result)

def home(request):
    context = {
        'total_customers': Customer.objects.values('customer_id').distinct().count(),
        'segments': ['YoungProfessional','FamilyWithChildren','EmptyNester','HighNetWorth','Entrepreneur','Student','Retiree'],
        'segment_labels': {
            'YoungProfessional': 'Jeunes Professionnels',
            'FamilyWithChildren': 'Familles avec Enfants',
            'EmptyNester': 'Nids Vides',
            'HighNetWorth': 'Haute Valeur Nette',
            'Entrepreneur': 'Entrepreneurs',
            'Student': 'Étudiants',
            'Retiree': 'Retraités'
        }
    }
    return render(request, 'innovation_agent/home.html', context)

@csrf_exempt
def generate_data(request):
    if request.method == 'POST':
        generate_synthetic_customers(num_customers=150)
        cache.clear()
        return JsonResponse({'status':'success', 'message':'Données synthétiques générées'})
    return JsonResponse({'error':'POST requis'}, status=400)

def analysis(request):
    segments = ['YoungProfessional','FamilyWithChildren','EmptyNester','HighNetWorth','Entrepreneur','Student','Retiree']
    counts = []
    for seg in segments:
        count = Customer.objects.filter(segment=seg).values('customer_id').distinct().count()
        counts.append(count)
    latest_quarter = Customer.objects.values('quarter').distinct().order_by('-quarter').first()
    latest_quarter = latest_quarter['quarter'] if latest_quarter else '2025-Q4'
    spending_by_seg = []
    for seg in segments:
        avg_spend = Customer.objects.filter(segment=seg, quarter=latest_quarter).aggregate(avg_spend=models.Avg('monthly_spending'))['avg_spend'] or 0
        spending_by_seg.append(round(avg_spend,0))
    return JsonResponse({
        'segments': segments,
        'counts': counts,
        'spending': spending_by_seg,
        'quarter': latest_quarter
    })

def segment_trend(request):
    segment = request.GET.get('segment', 'YoungProfessional')
    metric = request.GET.get('metric', 'monthly_spending')
    data = get_trend_over_quarters(segment, metric)
    return JsonResponse(data, safe=False)

def segment_adoption(request):
    segment = request.GET.get('segment', 'YoungProfessional')
    data = get_product_adoption(segment)
    return JsonResponse(data)

def get_recommendations(request):
    segment = request.GET.get('segment', 'YoungProfessional')
    growth_sim = request.GET.get('growth_simulator', None)
    if growth_sim:
        try:
            growth_sim = float(growth_sim)
        except:
            growth_sim = None
    
    # Map English segment keys to French for the AI
    segment_map = {
        'YoungProfessional': 'Jeunes Actifs',
        'FamilyWithChildren': 'Familles avec enfants',
        'EmptyNester': 'Nids Vides',
        'HighNetWorth': 'Hauts revenus',
        'Entrepreneur': 'Professionnels',
        'Student': 'Étudiants',
        'Retiree': 'Retraités'
    }
    segment_fr = segment_map.get(segment, segment)
    
    cache_key = f"rec_{segment}_{growth_sim}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)
    
    latest_quarter_obj = Customer.objects.values('quarter').distinct().order_by('-quarter').first()
    latest_quarter = latest_quarter_obj['quarter'] if latest_quarter_obj else '2025-Q4'
    stats = get_segment_stats(segment, latest_quarter)
    trends, _ = detect_trends(segment)
    if stats['count'] == 0:
        generate_synthetic_customers()
        stats = get_segment_stats(segment, latest_quarter)
        trends, _ = detect_trends(segment)
    
    recommendations = generate_innovation_recommendation(segment_fr, stats, trends, growth_sim)
    
    explanation = f"Basé sur {stats['count']} clients du segment {segment_fr}. "
    if stats.get('avg_age'):
        explanation += f"Âge moyen {stats['avg_age']} ans, "
    if stats.get('avg_income'):
        explanation += f"revenu {stats['avg_income']} TND, "
    explanation += f"dépenses {stats['avg_spending']} TND. "
    if trends:
        trend_parts = []
        for k, v in trends.items():
            if v != 0:
                label = k.replace('avg_', '')
                trend_parts.append(f"{label} {v}%")
        if trend_parts:
            explanation += "Tendances T/T : " + ", ".join(trend_parts)
    
    response_data = {
        'segment': segment,
        'segment_fr': segment_fr,
        'stats': stats,
        'trends': trends,
        'recommendations': recommendations,
        'explanation': explanation
    }
    cache.set(cache_key, response_data, 3600)
    cache.set(f"rec_{segment}_latest", response_data, 3600)
    return JsonResponse(response_data)

def generate_pdf_report(request):
    """
    Generate a professional PDF report for a single segment with clean formatting.
    """
    segment = request.GET.get('segment', 'YoungProfessional')
    
    segment_labels = {
        'YoungProfessional': 'Jeunes Professionnels',
        'FamilyWithChildren': 'Familles avec Enfants',
        'EmptyNester': 'Nids Vides',
        'HighNetWorth': 'Haute Valeur Nette',
        'Entrepreneur': 'Entrepreneurs',
        'Student': 'Étudiants',
        'Retiree': 'Retraités'
    }
    
    NAVY = colors.HexColor('#1A2A4A')
    NAVY_DEEP = colors.HexColor('#0F1A2E')
    RED = colors.HexColor('#E32227')
    SOFT_BLUE = colors.HexColor('#E8EEF9')
    MUTED = colors.HexColor('#6B7280')
    
    latest_quarter_obj = Customer.objects.values('quarter').distinct().order_by('-quarter').first()
    latest_quarter = latest_quarter_obj['quarter'] if latest_quarter_obj else '2025-Q4'
    
    stats = get_segment_stats(segment, latest_quarter)
    if stats['count'] == 0:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("Erreur", styles['Title']))
        story.append(Paragraph(f"Aucune donnée trouvée pour le segment {segment}.", styles['Normal']))
        doc.build(story)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="error_report.pdf"'
        return response
    
    trend_data = get_trend_over_quarters(segment, 'monthly_spending')
    adoption_data = get_product_adoption(segment)
    top_products = sorted(adoption_data.items(), key=lambda x: x[1], reverse=True)[:8]
    
    latest = cache.get(f"rec_{segment}_latest")
    if latest:
        recs = latest.get('recommendations', {})
    else:
        recs = {
            'trend_interpretation': '⚠️ Aucune recommandation disponible.',
            'product': 'Générer d\'abord les idées',
            'modification': 'Générer d\'abord les idées',
            'partnership': 'Générer d\'abord les idées',
            'justification': 'Générer d\'abord les idées',
            'roadmap': 'Générer d\'abord les idées',
            'risks': 'Générer d\'abord les idées'
        }
    
    # --- Helper to clean and format text for PDF ---
    def clean_pdf_text(text):
        if not text:
            return ''
        # Remove excessive whitespace and newlines
        text = ' '.join(text.split())
        # Convert ** to <b> tags for ReportLab
        parts = text.split('**')
        result = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                result.append(part)
            else:
                result.append(f"<b>{part}</b>")
        return ''.join(result)
    
    def split_into_paragraphs(text, max_len=600):
        """Split text into paragraphs for PDF."""
        if not text:
            return []
        # Clean and format
        text = clean_pdf_text(text)
        # Split by bullet points or newlines
        lines = text.split('\n')
        paragraphs = []
        for line in lines:
            if line.strip():
                paragraphs.append(line.strip())
        # If we have long paragraphs, split by sentences
        final = []
        for p in paragraphs:
            if len(p) > max_len:
                # Split by . followed by space
                sub = p.split('. ')
                for s in sub:
                    if s.strip():
                        final.append(s.strip() + '.')
            else:
                final.append(p)
        return final[:8]  # Limit to 8 lines to avoid overflow
    
    # --- Generate charts (unchanged) ---
    fig1, ax1 = plt.subplots(figsize=(6, 3))
    if trend_data:
        quarters = [d['quarter'] for d in trend_data]
        values = [d['value'] for d in trend_data]
        ax1.plot(quarters, values, marker='o', color='#27ae60', linewidth=2)
        ax1.set_title(f'Évolution des dépenses - {segment_labels.get(segment, segment)}', fontsize=10)
        ax1.set_ylabel('Dépenses moyennes (TND)')
        ax1.tick_params(axis='x', rotation=45)
        ax1.grid(True, linestyle='--', alpha=0.3)
    else:
        ax1.text(0.5, 0.5, 'Aucune donnée disponible', ha='center', va='center')
    plt.tight_layout()
    trend_img_buffer = BytesIO()
    plt.savefig(trend_img_buffer, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig1)
    trend_img_buffer.seek(0)
    
    fig2, ax2 = plt.subplots(figsize=(6, 3))
    if top_products:
        labels = [p[0] for p in top_products]
        values = [p[1] for p in top_products]
        colors_list = ['#2A4A7F' if i % 2 == 0 else '#E32227' for i in range(len(labels))]
        ax2.bar(labels, values, color=colors_list)
        ax2.set_title(f'Adoption des produits - {segment_labels.get(segment, segment)}', fontsize=10)
        ax2.set_ylabel('% de clients')
        ax2.tick_params(axis='x', rotation=45)
    else:
        ax2.text(0.5, 0.5, 'Aucun produit enregistré', ha='center', va='center')
    plt.tight_layout()
    adopt_img_buffer = BytesIO()
    plt.savefig(adopt_img_buffer, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig2)
    adopt_img_buffer.seek(0)
    
    # --- Build PDF ---
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    
    styles = getSampleStyleSheet()
    
    cover_title_style = ParagraphStyle(
        'CoverTitle', parent=styles['Title'],
        fontSize=28, textColor=colors.white, fontName=FONT_BOLD,
        alignment=TA_CENTER, spaceAfter=6, leading=32
    )
    cover_sub_style = ParagraphStyle(
        'CoverSub', parent=styles['Normal'],
        fontSize=14, textColor=colors.HexColor('#c8d2e6'), fontName=FONT_NAME,
        alignment=TA_CENTER, spaceAfter=12
    )
    section_title_style = ParagraphStyle(
        'SectionTitle', parent=styles['Heading1'],
        fontSize=20, textColor=NAVY, fontName=FONT_BOLD,
        spaceAfter=4, leading=24
    )
    section_eyebrow_style = ParagraphStyle(
        'SectionEyebrow', parent=styles['Normal'],
        fontSize=9, textColor=RED, fontName=FONT_BOLD,
        spaceAfter=6, letterSpacing=2
    )
    heading_style = ParagraphStyle(
        'Heading', parent=styles['Heading2'],
        fontSize=13, textColor=NAVY, fontName=FONT_BOLD,
        spaceAfter=8, spaceBefore=14
    )
    body_text_style = ParagraphStyle(
        'BodyText', parent=styles['Normal'],
        fontSize=10.5, textColor=colors.HexColor('#1F2937'), fontName=FONT_NAME,
        leading=16, alignment=TA_LEFT
    )
    small_text_style = ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontSize=8.5, textColor=MUTED, fontName=FONT_NAME,
        leading=12
    )
    reco_title_style = ParagraphStyle(
        'RecoTitle', parent=styles['Normal'],
        fontSize=11, textColor=NAVY, fontName=FONT_BOLD,
        spaceAfter=4
    )
    reco_body_style = ParagraphStyle(
        'RecoBody', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#1F2937'), fontName=FONT_NAME,
        leftIndent=8, leading=15
    )
    
    final_story = []
    
    # --- Cover page ---
    final_story.append(Spacer(1, 30*mm))
    final_story.append(Paragraph("BANQUE · RAPPORT CONFIDENTIEL", small_text_style))
    final_story.append(Spacer(1, 2*mm))
    final_story.append(Paragraph("Agent d'Innovation Produit Bancaire", 
                                  ParagraphStyle('BrandName2', parent=styles['Normal'], fontSize=14, textColor=colors.white, fontName=FONT_BOLD, spaceAfter=20)))
    final_story.append(Spacer(1, 25*mm))
    final_story.append(Paragraph("RAPPORT STRATÉGIQUE 2026", 
                                  ParagraphStyle('Eyebrow2', parent=styles['Normal'], fontSize=10, textColor=RED, fontName=FONT_BOLD, letterSpacing=3)))
    final_story.append(Spacer(1, 6*mm))
    final_story.append(Paragraph("Recommandations <font color='#E32227'>produits</font> & opportunités de croissance", cover_title_style))
    final_story.append(Spacer(1, 8*mm))
    final_story.append(Paragraph(f"Analyse du segment <b>{segment_labels.get(segment, segment)}</b> - {stats['count']} clients analysés", cover_sub_style))
    final_story.append(Spacer(1, 10*mm))
    
    div_data = [['']]
    div_table = Table(div_data, colWidths=[60*mm], rowHeights=[4])
    div_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), RED),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    final_story.append(div_table)
    final_story.append(Spacer(1, 30*mm))
    
    meta_data = [
        ['Date', 'Préparé pour', 'Référence'],
        [datetime.datetime.now().strftime('%d/%m/%Y'), 'Direction Produit', f'AIPB-{segment[:3]}-Q2-2026']
    ]
    meta_table = Table(meta_data, colWidths=[55*mm, 55*mm, 55*mm], rowHeights=[6*mm, 10*mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#97a4c2')),
        ('FONTNAME', (0,1), (-1,1), FONT_BOLD),
        ('FONTSIZE', (0,1), (-1,1), 12),
        ('TEXTCOLOR', (0,1), (-1,1), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    final_story.append(meta_table)
    final_story.append(PageBreak())
    
    # --- Executive Summary ---
    final_story.append(Paragraph("01 — SYNTHÈSE", section_eyebrow_style))
    final_story.append(Paragraph("Résumé exécutif", section_title_style))
    div_data2 = [['']]
    div_table2 = Table(div_data2, colWidths=[40*mm], rowHeights=[3])
    div_table2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), RED),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    final_story.append(div_table2)
    final_story.append(Spacer(1, 8*mm))
    
    final_story.append(Paragraph(
        f"Analyse de <b>{stats['count']}</b> clients du segment <b>{segment_labels.get(segment, segment)}</b>. "
        f"Revenu moyen : {stats.get('avg_income', 0):.0f} TND, dépenses : {stats.get('avg_spending', 0):.0f} TND.",
        body_text_style
    ))
    final_story.append(Spacer(1, 6*mm))
    
    kpi_data = [
        ['Clients analysés', 'Âge moyen', 'Revenu moyen', 'Dépenses'],
        [
            str(stats['count']),
            f"{stats.get('avg_age', 0):.1f} ans",
            f"{stats.get('avg_income', 0):,.0f} TND",
            f"{stats.get('avg_spending', 0):,.0f} TND"
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[40*mm, 40*mm, 40*mm, 40*mm], rowHeights=[12*mm, 14*mm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), SOFT_BLUE),
        ('BACKGROUND', (0,1), (-1,1), colors.white),
        ('FONTNAME', (0,0), (-1,0), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), MUTED),
        ('FONTNAME', (0,1), (-1,1), FONT_BOLD),
        ('FONTSIZE', (0,1), (-1,1), 14),
        ('TEXTCOLOR', (0,1), (-1,1), NAVY),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    final_story.append(kpi_table)
    final_story.append(Spacer(1, 8*mm))
    
    final_story.append(Paragraph("Conclusions clés", heading_style))
    final_story.append(Paragraph(
        f"• Âge moyen : {stats.get('avg_age', 0):.1f} ans. Épargne : {stats.get('avg_savings', 0):.0f} TND.",
        body_text_style
    ))
    final_story.append(Paragraph(
        f"• Taux de détention : {stats.get('avg_products_held', 0):.1f} produits par client.",
        body_text_style
    ))
    final_story.append(Paragraph(
        f"• Engagement mobile : {stats.get('avg_mobile', 0):.1f}/10, en ligne : {stats.get('avg_online', 0):.1f}/10.",
        body_text_style
    ))
    final_story.append(Spacer(1, 6*mm))
    
    callout_data = [[f'"L\'analyse du segment {segment_labels.get(segment, segment)} révèle des opportunités de développement produit ciblées."']]
    callout_table = Table(callout_data, colWidths=[160*mm], rowHeights=[18*mm])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY_DEEP),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('LEFTINDENT', (0,0), (-1,-1), 30),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    final_story.append(callout_table)
    final_story.append(Spacer(1, 4*mm))
    final_story.append(Paragraph("— Agent d'Innovation Produit", small_text_style))
    final_story.append(PageBreak())
    
    # --- Segment Analysis ---
    final_story.append(Paragraph("02 — ANALYSE DU SEGMENT", section_eyebrow_style))
    final_story.append(Paragraph(f"Profil du segment {segment_labels.get(segment, segment)}", section_title_style))
    final_story.append(div_table2)
    final_story.append(Spacer(1, 8*mm))
    
    stats_data = [
        ['Indicateur', 'Valeur', 'Indicateur', 'Valeur'],
        ['Clients', str(stats['count']), 'Âge moyen', f"{stats.get('avg_age', 0):.1f} ans"],
        ['Revenu', f"{stats.get('avg_income', 0):.0f} TND", 'Dépenses', f"{stats.get('avg_spending', 0):.0f} TND"],
        ['Épargne', f"{stats.get('avg_savings', 0):.0f} TND", 'Produits', f"{stats.get('avg_products_held', 0):.1f}"],
    ]
    stats_table = Table(stats_data, colWidths=[40*mm, 40*mm, 40*mm, 40*mm], rowHeights=[6*mm]*4)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), FONT_BOLD),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('FONTNAME', (0,1), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
    ]))
    final_story.append(stats_table)
    final_story.append(Spacer(1, 10*mm))
    
    if trend_data:
        final_story.append(Paragraph("Évolution des dépenses par trimestre", heading_style))
        trend_img = Image(trend_img_buffer, width=140*mm, height=70*mm)
        final_story.append(trend_img)
    final_story.append(Spacer(1, 6*mm))
    
    if top_products:
        final_story.append(Paragraph("Adoption des produits", heading_style))
        adopt_img = Image(adopt_img_buffer, width=140*mm, height=70*mm)
        final_story.append(adopt_img)
    final_story.append(Spacer(1, 6*mm))
    
    if top_products:
        prod_text = "Top produits : " + ", ".join([f"<b>{p[0]}</b> ({p[1]}%)" for p in top_products[:5]])
        final_story.append(Paragraph(prod_text, body_text_style))
    
    final_story.append(PageBreak())
    
    # --- AI Recommendations ---
    final_story.append(Paragraph("03 — RECOMMANDATIONS IA", section_eyebrow_style))
    final_story.append(Paragraph("Stratégie produit générée par l'agent", section_title_style))
    final_story.append(div_table2)
    final_story.append(Spacer(1, 6*mm))
    
    # Clean and display each recommendation section
    sections = [
    ('▸', 'Interprétation stratégique', recs.get('trend_interpretation', '')),
    ('▸', 'Nouveau produit recommandé', recs.get('product', '')),
    ('▸', 'Modification de produit', recs.get('modification', '')),
    ('▸', 'Partenariat stratégique', recs.get('partnership', '')),
    ('▸', 'Justification métier & ROI', recs.get('justification', '')),
    ('▸', 'Plan de déploiement', recs.get('roadmap', '')),
    ('▸', 'Risques et mitigation', recs.get('risks', ''))
    ]
    
    for icon, title, content in sections:
        if content and len(content) > 10:
            # Clean and split content
            cleaned = clean_pdf_text(content)
            # Split into paragraphs
            paragraphs = split_into_paragraphs(content, max_len=350)
            if paragraphs:
                final_story.append(Paragraph(f"{icon} <b>{title}</b>", reco_title_style))
                for para in paragraphs[:6]:  # Limit to 6 lines
                    if para.strip():
                        # Convert ** to bold already done in split_into_paragraphs
                        final_story.append(Paragraph(para, reco_body_style))
                final_story.append(Spacer(1, 4*mm))
    
    final_story.append(PageBreak())
    
    # --- Action Plan ---
    final_story.append(Paragraph("04 — PLAN D'ACTION", section_eyebrow_style))
    final_story.append(Paragraph("Prochaines étapes", section_title_style))
    final_story.append(div_table2)
    final_story.append(Spacer(1, 8*mm))
    
    action_data = [
        ['Phase', 'Action', 'Responsable', 'Échéance'],
        ['1 · Cadrage', 'Validation business case', 'Direction Produit', 'M+1'],
        ['2 · Design', 'Prototypage UX', 'Studio Design', 'M+2'],
        ['3 · Build', 'Développement technique', 'Tech & IT', 'M+4'],
        ['4 · Pilote', 'Lancement test 3 régions', 'Marketing', 'M+6'],
        ['5 · Scale', 'Déploiement national', 'Direction Générale', 'M+8'],
    ]
    action_table = Table(action_data, colWidths=[30*mm, 50*mm, 40*mm, 30*mm], rowHeights=[7*mm]*6)
    action_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), FONT_BOLD),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('FONTNAME', (0,1), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
    ]))
    final_story.append(action_table)
    final_story.append(Spacer(1, 8*mm))
    
    risk_text = recs.get('risks', 'Risques : concurrence, adoption lente, réglementation.')
    if risk_text == 'Non disponible' or len(risk_text) < 10:
        risk_text = 'Risques identifiés : concurrence locale, adoption lente par les clients, évolutions réglementaires.'
    
    # Clean risk text for display
    risk_cleaned = clean_pdf_text(risk_text)
    
    two_col_data = [
        [Paragraph("<b>Risques identifiés</b>", heading_style), Paragraph("<b>Hypothèses clés</b>", heading_style)],
        [Paragraph(risk_cleaned[:500], body_text_style), 
         Paragraph("Taux de conversion : 4,2%<br/>Churn mensuel : < 1,8%<br/>Coût d'acquisition : ≤ 38 TND", body_text_style)]
    ]
    two_col_table = Table(two_col_data, colWidths=[75*mm, 75*mm], rowHeights=[10*mm, 35*mm])
    two_col_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    final_story.append(two_col_table)
    final_story.append(Spacer(1, 6*mm))

    final_story.append(Spacer(1, 4*mm))
    final_story.append(Paragraph("— Direction de l'Innovation", small_text_style))
    
    # Build document with cover page
    def cover_builder_final(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY_DEEP)
        canvas.rect(0, 0, doc.width + 2*doc.leftMargin, doc.height + 2*doc.topMargin, fill=1)
        canvas.setFillColor(colors.HexColor('#e32227'))
        canvas.setFillAlpha(0.15)
        canvas.circle(doc.width + doc.leftMargin - 30, doc.height + doc.topMargin - 30, 250, fill=1)
        canvas.setFillAlpha(1)
        canvas.setFillColor(RED)
        canvas.rect(0, 0, doc.width + 2*doc.leftMargin, 5, fill=1)
        canvas.restoreState()
    
    doc.build(final_story, onFirstPage=cover_builder_final)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="innovation_report_{segment}_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
    return response