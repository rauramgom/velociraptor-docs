import urllib.request
import json
import yaml
import re
import os
from zipfile import ZipFile

# Where we generate the search index.
commits_url = "https://api.github.com/repos/Velocidex/velociraptor-docs/commits"
output_data_path = "static/exchange/data.json"
archive_path = "static/exchange/artifact_exchange.zip"
artifact_root_directory = "content/exchange/artifacts"
artifact_page_directory = "content/exchange/artifacts/pages"

org = "Velocidex"
project = "velociraptor-docs"

# Each yaml file will be converted to a markdown if needed.
template = """---
title: %s
hidden: true
editURL: https://github.com/%s/%s/edit/master/%s
---

%s

```yaml
%s
```
"""

previous_data = []
try:
  with open(output_data_path) as fd:
    previous_data = json.loads(fd.read())
except:
  pass

date_regex = re.compile("^[0-9]{4}-[0-9]{2}-[0-9]{2}")
hash_regex = re.compile("#([0-9_a-z]+)", re.I | re.M | re.S)

def cleanDescription(description):
  return hash_regex.sub("", description)

def cleanupDate(date):
  try:
    return date.strftime("%Y-%m-%d")
  except AttributeError:
    m = date_regex.match(date)
    if m:
      return m.group(0)
  return date

def getTags(description):
  result = []
  for m in hash_regex.finditer(description):
    result.append(m.group(1))

  return result

def getAuthor(record, yaml_filename):
  # If the record already exists, just keep it the same
  title = record["title"]
  for item in previous_data:
    if item["title"] == title:
      return item

  # Get commit details for this file.
  path = yaml_filename.replace("\\", "/")
  commits = json.loads(urllib.request.urlopen(commits_url + "?path=" + path).read())
  print("Checking commit for %s\n" % path)

  # Commit is not yet know.
  if not commits:
    print("No commits yet\n")
    record["author"] = ""
    record["author_link"] = ""
    record["author_avatar"] = ""
    record["date"] = ""
    return record

  first_commit = commits[-1]
  record["author"] = first_commit["author"]["login"]
  record["author_link"] = first_commit["author"]["html_url"]
  record["author_avatar"] = first_commit["author"]["avatar_url"]
  record["date"] = cleanupDate(first_commit["commit"]["author"]["date"])

  print("Commit by %s\n" % record["author"])
  return record

# Create a zip file with all the artifacts in it.
def make_archive():
  with ZipFile(archive_path, mode='w') as archive:
    for root, dirs, files in os.walk(artifact_root_directory):
      for name in files:
        if not name.endswith(".yaml"):
          continue

        archive.write(os.path.join(root, name))

def build_markdown():
  index = []

  for root, dirs, files in os.walk(artifact_root_directory):
    files.sort()

    for name in files:
      if not name.endswith(".yaml"):
        continue

      yaml_filename = os.path.join(root, name)
      with open(yaml_filename) as stream:
        content = stream.read()
        data = yaml.safe_load(content)

        base_name = os.path.splitext(yaml_filename)[0]
        base_name = os.path.relpath(base_name, artifact_root_directory)
        filename_name = os.path.join(artifact_page_directory, base_name)

        description = data.get("description", "")

        index.append(getAuthor({
          "title": data["name"],
          "author": data.get("author"),
          "description": cleanDescription(description),
          "link": os.path.join("/exchange/artifacts/pages/",
                               base_name.lower()).replace("\\", "/"),
          "tags": getTags(description),
        }, yaml_filename))

        md_filename = filename_name + ".md"
        with open(md_filename, "w") as fd:
           fd.write(template % (data["name"], org, project,
                                yaml_filename,
                                data["description"], content))

  index = sorted(index, key=lambda x: x["date"],
                 reverse=True)

  with open(output_data_path, "w") as fd:
    fd.write(json.dumps(index, indent=4))
    print("Writing data.json in %s" % output_data_path)

if __name__ == "__main__":
  build_markdown()
  make_archive()


if os.getenv('CI'):
   # Remove this file so the site may be pushed correctly.
   os.remove(artifact_root_directory + "/.gitignore")
   os.remove(os.path.dirname(output_data_path) + "/.gitignore")
