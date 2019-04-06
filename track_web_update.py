# Python code to track a particular change in website
import requests
from bs4 import BeautifulSoup

# website_link = "http://www.ietdavv.edu.in/index.php/notices"
website_link = "http://www.ietdavv.edu.in/index.php"
print("connecting .... ")
res = requests.get(website_link)
print("connected.")
print(res.status_code)

print("Writing to file ...")
file = open("web.html", "w")

print(res.headers)

print("Performing Analysis")
soup = BeautifulSoup(res.text, 'html.parser')
# notice_section_start_string = '<div itemprop="articleBody">'
# notice_section_end_string = '</div>'

# start_index = text.find(notice_section_start_string)
# end_index = (text[start_index:]).find(notice_section_end_string)
# end_index = start_index + end_index
# print(start_index, end_index)
# parser.feed(text[start_index:end_index])
file.write(soup.prettify())
file.close()
print("Wrote to file.")

# notice_section = soup.find("div", itemprop="articleBody")
# for l in notice_section.find_all("a"):
#     print(l.string)
latest_section = soup.find("div", "mod_placehere_leading")
for notice in latest_section.find_all("a"):
    print(notice.string)
