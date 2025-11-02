import requests
import re
import sys

def extract_article_content(article_url):
    """Test version of extract_article_content"""
    print(f"\n=== Testing URL: {article_url} ===\n")
    
    try:
        r = requests.get(article_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        print(f"Status Code: {r.status_code}")
        
        if r.status_code == 200:
            html = r.text or ''
            print(f"HTML Length: {len(html)} chars\n")
            
            # Extract title
            title = None
            m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
                print(f"✓ Found OG Title: {title}")
            else:
                m2 = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                if m2:
                    title = m2.group(1).strip()
                    print(f"✓ Found <title>: {title}")
            
            # Extract description
            description = None
            m_desc = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if m_desc:
                description = m_desc.group(1).strip()
                print(f"✓ Found OG Description: {description[:100]}...")
            else:
                m_desc2 = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if m_desc2:
                    description = m_desc2.group(1).strip()
                    print(f"✓ Found meta description: {description[:100]}...")
            
            # Extract article body
            article_body = None
            article_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.IGNORECASE | re.DOTALL)
            if article_match:
                article_html = article_match.group(1)
                article_html = re.sub(r'<script[^>]*>.*?</script>', '', article_html, flags=re.IGNORECASE | re.DOTALL)
                article_html = re.sub(r'<style[^>]*>.*?</style>', '', article_html, flags=re.IGNORECASE | re.DOTALL)
                paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', article_html, re.IGNORECASE | re.DOTALL)
                
                if paragraphs:
                    print(f"✓ Found {len(paragraphs)} paragraphs in <article>")
                    clean_paras = []
                    for p in paragraphs[:5]:
                        clean_p = re.sub(r'<[^>]+>', '', p).strip()
                        if len(clean_p) > 30:
                            clean_paras.append(clean_p)
                            print(f"  - Para: {clean_p[:80]}...")
                    
                    if clean_paras:
                        article_body = ' '.join(clean_paras)
            else:
                print("✗ No <article> tag found")
            
            # Combine
            combined_text = []
            if title:
                combined_text.append(title)
            if description and description not in (title or ''):
                combined_text.append(description)
            if article_body:
                if len(article_body) > 1000:
                    article_body = article_body[:1000] + '...'
                combined_text.append(article_body)
            
            if combined_text:
                full_text = ' | '.join(combined_text)
                print(f"\n=== FINAL EXTRACTED CONTENT ===")
                print(f"Length: {len(full_text)} chars")
                print(f"Content: {full_text[:300]}...")
                return {"status": "success", "content": full_text, "title": title}
            else:
                print("\n✗ No content extracted")
                
    except Exception as e:
        print(f"✗ Error: {e}")
    
    return {"status": "not_found", "message": "Could not extract content"}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter a news URL to test: ")
    
    result = extract_article_content(url)
    print(f"\n=== RESULT ===")
    print(result)
