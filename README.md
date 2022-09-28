# Colby.edu Platform Site

## API Endpoints

### All courses for an academic year
https://www.colby.edu/endpoints/v1/courses/

### All courses for a department
https://www.colby.edu/endpoints/v1/subjectcourses/AR (Art used)

### Majors and Minors (not final)

https://www.colby.edu/endpoints/v1/majorsminors

### 5 Curated News Stories
https://feature-wp-api-r2smz6y-4nvswumupeimi.us-4.platformsh.site/wp-json/wp/v2/posts?per_page=5&tags=561&_embed=1 (we'll release this to news.colby.edu when approved)


Field mappings:

- Headline - title.rendered
- Primary Category - post-meta-fields.primary_category
- URL - link
- Summary - post-meta-fields.summary
- Image - everything can be found in media_details, not sure what you need exactly

### Directory Data

Example Workday Data:

```json
{
	"Report_Entry": [
		{
			"CF_Adjusted_Work_Email":"joe.blow@colby.edu",
			"supervisoryOrganization":"President's Office - JM (Jane Doe)",
			"CF_Superior_Org_Level_09_ID":null,
			"CF_Superior_Org_Level_05_ID":null,
			"Superior_Organization_Level_07_Away":null,
			"Superior_Organization_Level_10_Away":null,
			"suffix":null,
			"organizationsManaged":null,
			"primaryWorkEmail":"joe.blow@colby.edu",
			"CF_Executive_Level_Assigned_Organization":"EX120 Vice President and Chief Financial Officer",
			"Superior_Organization_Level_08_Away":null,
			"businessTitle":"Professor; Dean of the College, Emeritus; College Historian",
			"Academic_Units":"Colby College",
			"CF_Superior_Org_Level_01_ID":"xxxxxxxxxxx",
			"superiorOrgID":"xxxxxxxxxxx",
			"preferredSuffix":null,
			"Superior_Organization_Level_01_Away":"President's Office (David Greene)",
			"CF_Superior_Org_Level_06_ID":null,
			"workAddressCity":"Waterville",
			"workSpaceSuperiorLocation":null,
			"workAddress1":"4000 Mayflower Hill Drive",
			"referenceID":"xxxxxxxxx",
			"Superior_Organization_Level_05_Away":null,
			"Superior_Organization_Level_02_Away":"Colby College (David Greene)",
			"firstName":"Joe",
			"Job_Family_Group":"Administration",
			"CF_Superior_Org_Level_02_ID":"xxxxxxx",
			"salutation":null,
			"Cost_Center_ID":"xxxxxxxxxx",
			"lastName":"Blow",
			"workSpaceLocation":null,
			"primaryWorkPhone":null,
			"jobFamilyGroup":"Administration",
			"workerPhotos":null,
			"CF_Superior_Org_Level_03_ID":null,
			"orgDisplayID":"President's Office - JM (Jane Doe)",
			"CF_Superior_Org_Level_07_ID":null,
			"employeeID":"xxxxxxxxxxxx",
			"Superior_Organization_Level_04_Away":null,
			"Cost_Center_Name":"College Historian",
			"CF_Superior_Org_Level_10_ID":null,
			"CF_Has_Sabbatical_Leave_Type":"0",
			"CF_Superior_Org_Level_04_ID":null,
			"Superior_Organization_Level_03_Away":null,
			"CF_Superior_Org_Level_08_ID":null,
			"supervisoryOrgHierarchy":"Colby College (David Greene) > President's Office (David Greene) > President's Office - JM (Jane Doe)",
			"superiorOrg":"President's Office (David Greene)",
			"jobProfileName":"College Historian",
			"employeeType":"Temporary",
			"workAddressState":"Maine",
			"preferredFirstName":"Joe",
			"workdayID":"xxxxxxxxxxxx",
			"workAddressCountry":"United States of America",
			"middleName":"H.",
			"location":"Colby College",
			"workAddressPostalCode":"04901",
			"Superior_Organization_Level_06_Away":null,
			"primaryWorkSpace":null,
			"Superior_Organization_Level_09_Away":null
		},
		...
	]
}

```

CX Profile JSON Endpoint: https://cxweb.colby.edu/webservices/profilejson/brandon.waltz/web

We can probably use the CX data to get all the data we need as the fields: homephone, country, address1, address2, firstname, lastname, state, cellphone, zip, building, room, suffixname, dept, city, middlename, nickname or (preferred name), phone are synced with Workday every hour. The CX data has the bios.

We'll still need to get titles from the Workday data as those are not synced with CX, so CX will be inaccurate.

We'll probably need some cron job that pulls the WD data and rebuilds the directory every day to keep it up to date when new people come or people leave. But most of the fields, beside title, can come from CX.

I don't believe any API has pronouns. This will most likely need to come from WP.

***

## How to Use This Repo as a Template

1. Click "Use this Template" button
2. Create it in the Colby Communications organization under the naming convention `[sitename]-site`
3. Clone on local machine
4. Add [sitename] to the following files, replacing placeholder text:

- composer.json
- .platform.app.yaml
- .lando.yaml
- README.md

5. Create an upstream to the starter repo via `git remote add upstream https://github.com/ColbyCommunications/platformsh-wp-starter`

6. Link with Platform.sh:

- Create blank project in Platform.sh console
- Add Platform.sh repo as remote: `platform project:set-remote [project_id]`

## How to Navigate the Project

### Composer and Dependencies

All free wordpress plugins and themes are dependencies of the project and are pulled in via Composer and composer.json. Free plugins and themes are typically found on <a href="https://wpackagist.org/">WP Packagist</a>. The use of composer makes it easy to tie plugins and themes down to a specific version with composer's [versioning syntax](https://getcomposer.org/doc/articles/versions.md).

Premium plugins/themes need to be committed to the repository and put in the `web/wp-content` directory. When doing this, you'll also need to modify the .gitignore file to make sure you expose the new plugin/theme to git.

When no composer.lock is present, you can just run `composer install` to get all fresh dependencies. If a composer.lock is present, you'll need to run `composer update` to update currently installed dependecies. For example, when making changes to a Colby plugin or theme, it is common to then pull those in via a `composer update` command.

### Scripts

All scripts for the project are found in the `scripts` directory. Scripts are run at different times during development, build and deploy on Platform.sh. You can see how scripts are invoked by following the trail from `.platform.app.yaml` or `lando.yaml`.

### Lando Local Development

You'll need docker and lando installed in order to run a local version of the project on your machine. After those pre-reqs are install and after you `cd` into this project. You should be easily able to run `lando start` to start the local server and `lando stop` to stop it. You can say `no` to any prompts. If you change your lando yaml config anytime after you've set up the initial project, you'll need to run `lando rebuild -y` to rebuild with the new config.

### Setup

When setting up the site for the first time inside platform, the root user should always be `webmaster@colby.edu`. The password should be different than any used in the past. We keep track of these passwords in the Office LastPass.

### Helpful Commands

`platform db:dump` - dumps the database from the current Platform.sh environment and downloads it to the project folder  
`platform mount:download --mount="web/wp-content/uploads" --target="web/wp-content/uploads"` - downloads all media uploads from the current Platform.sh environment  
`platform environment:activate` - activates the current environment (mostly used for dev branches)  
`platform ssh` - ssh tunnels into current Platform.sh cloud container  
`platform sql < [dump].sql` - replaces current Platform.sh database data with a local dump file

## Change Log

### 3.0.0

- adds support for PHP 8.0
- upgrades Wordpress to 6.0
- upgrades WP SAML Auth Plugin to 2.\*
- upgrades Yoast plugin to 19.3

### 2.1.0

- adds github actions for interacting with Platform repos
- adds support for satis.colby.edu
- remove redis
- upgrade node in Platform.sh CI to v16
- move Platform.sh dependencies, WP CLI mostly, to composer
- removes unneccesary .platform.template.yaml file
- removes baseinstall
- updates lando to PHP 7.4
- removes disk.yaml and runtime.extensions.yaml in favor of putting those right in .platform.app.yaml
- new format for .npmrc
- simplify lando build - get rid of platform sync prompt
- adds support for composer allowedPlugins
- adds support for .env files + generation scripts
- moves Platform CI to composer 2
- adds WP Search with Algolia Plugin

### 2.0.1

- patch for wrong wpgraphql version

### 2.0.0

- update plugins: elementor-pro, jet plugins, ACF, gravityforms, yoast
