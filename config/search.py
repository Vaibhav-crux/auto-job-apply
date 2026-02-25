# Enter your search terms inside '[ ]' with quotes ' "searching title" ' for each search followed by comma ', ' Eg: ["Software Engineer", "Software Developer", "Selenium Developer"]
search_terms = ["Backend Python Developer", "Product Security"]
# search_terms = ["Product Security", "Security", "Application Security", "Web Security"]

# Define how many search terms you want to use
search_terms_counts = 2

# Skip search terms if founded in options
skip_search_terms = ["Intern","Fresher", "Trainee"]

# Search location, this will be filled in "City, state, or zip code" search box. If left empty as "", tool will not fill it.
search_location = "India"               # Some valid examples: "", "United States", "India", "Chicago, Illinois, United States", "90001, Los Angeles, California, United States", "Bengaluru, Karnataka, India", etc.

# Total years of experience. If provided as -1, tool will not fill it.
experience_years = 4

# Add work mode if you want to filter jobs by work mode, leave empty if you don't want to filter by work mode
work_mode = [] #["Work from office", "Hybrid", "Remote"]

# Add salary if you want to filter jobs by salary, leave -1 if you don't want to filter by salary
salary = -1

# Freshness of job to be applied
date_posted = 3 # 1 for Past 24 hours, 3 for Past 3 days, 7 for Past week, 15 for Past 15 days, 30 for Past 30 days

# Skip company jobs if founded in job posting
skip_company_jobs = ["Accenture", "TCS", "Infosys", "Wipro", "HCL", "Tata Consultancy Services"]