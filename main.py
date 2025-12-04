from eLiburutegiaAPI.eLiburutegia_api import *

SEARCH_URL_EUS = 'https://www.euskadi.eus/ac37aELiburutegiaPublicaWar/buscar?locale=eu&idioma=eu&formato=1|200|2|201|7|20'
DOWNLOAD_PATH = "app/downloads/"

def download_page(books: list[book]):
   home_session = init_session()
   for book in books:
      result = download_to_disk(book, home_session, DOWNLOAD_PATH)
      if result == 1:
         return 1
      elif result == -1:
         print(f"\nError downloading book '{book.name}' (ID: {book.id})")

   return 0

def download_all_new_books():
   page = 1
   books, result_count = search_book_basic("", page, input_search_url = SEARCH_URL_EUS)

   max_pages = int(result_count / 8) + (1 if result_count % 8 != 0 else 0)
   print(f"Total pages to process: {max_pages}")

   while page < max_pages:
      books, result_count = search_book_basic("", page, input_search_url = SEARCH_URL_EUS)
      print(f"\rDownloading page {page}/{max_pages}...", end="", flush=True)
      download_result = download_page(books)
      if download_result == 1:
         print(f"\nA book already exists. Exiting program.")
         return
      page += 1

   print("\nDownload process completed!")


download_all_new_books()