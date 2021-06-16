import camelot


filepath = "AVENUE APRIL 21.pdf"

tables = camelot.read_pdf(filepath, flavor='stream', table_areas=['160,309,3221,2352'],columns=['777,977,1130,1283,1441,1628,1820,2008,2221,2407,2550,2690,2891'])
