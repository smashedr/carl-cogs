from bs4 import BeautifulSoup

html = '''
<table class="wikitable sortable jquery-tablesorter" style="border: 1px solid darkgray; --darkreader-inline-border-top: #484e51; --darkreader-inline-border-right: #484e51; --darkreader-inline-border-bottom: #484e51; --darkreader-inline-border-left: #484e51;" data-darkreader-inline-border-top="" data-darkreader-inline-border-right="" data-darkreader-inline-border-bottom="" data-darkreader-inline-border-left="">
<caption>ICAO aircraft type designators
</caption>
<thead><tr>
<th scope="col" class="headerSort" tabindex="0" role="columnheader button" title="Sort ascending">ICAO<br>code<sup id="cite_ref-ICAOcode_3-0" class="reference"><a href="#cite_note-ICAOcode-3">[3]</a></sup>
</th>
<th scope="col" class="headerSort" tabindex="0" role="columnheader button" title="Sort ascending">IATA<br>type code
</th>
<th scope="col" class="headerSort" tabindex="0" role="columnheader button" title="Sort ascending">Model
</th></tr></thead><tbody>
<tr>
<td>A124</td>
<td>A4F</td>
<td><a href="/wiki/Antonov_An-124_Ruslan" title="Antonov An-124 Ruslan">Antonov An-124 Ruslan</a>
</td></tr>
<tr>
<td>A140</td>
<td>A40</td>
<td><a href="/wiki/Antonov_An-140" title="Antonov An-140">Antonov An-140</a>
</td></tr>
<tr>
<td>A148</td>
<td>A81</td>
<td><a href="/wiki/Antonov_An-148" title="Antonov An-148">Antonov An-148</a>
</td></tr>
<tr>
<td>A158</td>
<td>A58</td>
<td><a href="/wiki/Antonov_An-148#Variants" title="Antonov An-148">Antonov An-158</a>
</td></tr>
</tbody><tfoot></tfoot></table>
'''

# Parse the HTML using BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')

# Find all the table rows (excluding header and footer)
rows = soup.find('table').find('tbody').find_all('tr')

# Search for the given ICAO type code and retrieve the corresponding href
icao_code = 'A148'  # Example ICAO type code to search for

for row in rows:
    columns = row.find_all('td')
    if columns[0].text.strip() == icao_code:
        model_href = columns[2].find('a')['href']
        print(model_href)
        break
