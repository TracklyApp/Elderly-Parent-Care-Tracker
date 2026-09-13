"""Build the PDF and in-app chapter data from a single English source."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'data/pdf-tools'))
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
from pypdf import PdfReader
import pymupdf as fitz

data=json.loads((ROOT/'manual.json').read_text(encoding='utf-8'))
(ROOT/'guide-data.js').write_text('window.KindredGuide='+json.dumps(data,ensure_ascii=False)+';\n',encoding='utf-8')
out=ROOT/'output/pdf';out.mkdir(parents=True,exist_ok=True)
qa=ROOT/'tmp/pdfs';qa.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('Guide','C:/Windows/Fonts/segoeui.ttf'))
pdfmetrics.registerFont(TTFont('GuideBold','C:/Windows/Fonts/segoeuib.ttf'))
green=colors.HexColor('#28674f');ink=colors.HexColor('#243c33');muted=colors.HexColor('#62796c')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='GuideText',fontName='Guide',fontSize=10,leading=14.4,textColor=ink,spaceAfter=7))
styles.add(ParagraphStyle(name='GuideIntro',parent=styles['GuideText'],fontSize=11,leading=16,textColor=muted,spaceAfter=18))
styles.add(ParagraphStyle(name='GuideLabel',parent=styles['GuideText'],fontName='GuideBold',fontSize=9,textColor=green,spaceAfter=14))
styles.add(ParagraphStyle(name='GuideTitle',fontName='GuideBold',fontSize=27,leading=33,textColor=ink,spaceAfter=16))
styles.add(ParagraphStyle(name='GuideSub',parent=styles['GuideText'],fontName='GuideBold',fontSize=12,leading=16,spaceBefore=11,spaceAfter=7,keepWithNext=True))
styles.add(ParagraphStyle(name='GuideList',parent=styles['GuideText'],leftIndent=16,firstLineIndent=-16,spaceAfter=5))
def para(text,style='GuideText'):return Paragraph(escape(text),styles[style])
class GuideDoc(SimpleDocTemplate):
 def afterFlowable(self,f):
  if hasattr(f,'bookmark'):self.canv.bookmarkPage(f.bookmark);self.canv.addOutlineEntry(f.getPlainText(),f.bookmark,0)
def footer(c,doc):
 c.saveState();w,h=A4;c.setStrokeColor(colors.HexColor('#dee7df'));c.line(48,48,w-48,48);c.setFont('Guide',8);c.setFillColor(muted);c.drawString(48,34,'KINDRED  |  User Guide  |  September 2026');c.drawRightString(w-48,34,str(doc.page));c.setFillColor(green);c.rect(48,h-35,30,3,fill=1,stroke=0);c.restoreState()
story=[Spacer(1,20),para('KINDRED / THE LOCAL CARE APP','GuideLabel'),para(data['title'],'GuideTitle'),para(data['subtitle'],'GuideIntro'),para('A practical reference for parents, caregivers and family members. Start with a chapter below, or use User Guide inside the application to search the same instructions.'),Spacer(1,15),para('Contents','GuideSub')]
rows=[]
for i,s in enumerate(data['sections']):rows.append([para(f'{i+1:02}','GuideLabel'),Paragraph(f'<link href="#{s["id"]}" color="#28674f">{escape(s["title"])}</link>',styles['GuideText']),para(str(i+2))])
table=Table(rows,colWidths=[32,420,28]);table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#e5ece5'))]));story+=[table,Spacer(1,17),para('This manual contains no personal care records. Kindred supports care organization and recordkeeping; it does not provide medical advice.','GuideText')]
for i,s in enumerate(data['sections']):
 story.append(PageBreak());story.append(para(f'CHAPTER {i+1:02} / USER GUIDE','GuideLabel'));title=para(s['title'],'GuideTitle');title.bookmark=s['id'];story.extend([title,para(s['intro'],'GuideIntro')])
 for block in s['blocks']:
  story.append(para(block['title'],'GuideSub'))
  if 'text' in block:story.append(para(block['text']))
  for n,text in enumerate(block.get('steps',[]),1):story.append(para(f'{n}.  {text}','GuideList'))
  for text in block.get('bullets',[]):story.append(para('-  '+text,'GuideList'))
pdf=out/'Kindred-User-Guide.pdf'
doc=GuideDoc(str(pdf),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=54,bottomMargin=65,title=data['title'],author='Kindred',subject='Local application user manual')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
reader=PdfReader(pdf);assert len(reader.pages)==len(data['sections'])+1,f'Unexpected pagination: {len(reader.pages)}'
for i,s in enumerate(data['sections'],1):assert s['title'] in ' '.join(reader.pages[i].extract_text().split())
rendered=fitz.open(pdf)
for i,page in enumerate(rendered):page.get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(str(qa/f'manual-{i+1:02}.png'))
from PIL import Image,ImageOps,ImageDraw
thumbs=[]
for i in range(len(rendered)):
 im=Image.open(qa/f'manual-{i+1:02}.png').convert('RGB');im.thumbnail((238,337));tile=Image.new('RGB',(258,367),'#e5e9e5');tile.paste(im,((258-im.width)//2,10));ImageDraw.Draw(tile).text((12,348),f'Page {i+1}',fill='black');thumbs.append(tile)
sheet=Image.new('RGB',(258*4,367*((len(thumbs)+3)//4)),'white')
for i,im in enumerate(thumbs):sheet.paste(im,((i%4)*258,(i//4)*367))
sheet.save(qa/'contact-sheet.png')
print(f'Created {pdf} | {len(reader.pages)} pages | all chapter headings verified')
