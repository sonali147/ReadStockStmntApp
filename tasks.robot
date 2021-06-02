*** Settings ***
Documentation     Read the text contained in PDF files and save it to a
...               corresponding text file.
Library           RPA.PDF
Library           RPA.FileSystem
Library           RPA.HTTP
Library           RPA.JSON
Library           RPA.Dialogs
Library    String


*** Variables ***
${TXT_OUTPUT_DIRECTORY_PATH}=    ${CURDIR}${/}output${/}

*** Keywords ***
Collect Search Query From User
    Add Text Input    Search Query    search
    ${response}=    Run dialog
    [Return]    ${response.search}

*** Keywords ***
Collect PDF Files From User
    Add heading    Upload PDF File
    Add file input    
    ...    name=multiple    
    ...    label=Upload the PDF Files    
    ...    source=${CURDIR}${/}sample    
    ...    destination=${CURDIR}${/}uploads    
    ...    multiple=True    
    ...    file_type=PDF files (*.pdf)
    ${response}=    Run dialog
    FOR    ${path}    IN    @{response.multiple}
        Log    ${path}
    END
    [Return]    ${response.multiple}

*** Keywords ***
Extract text from PDF file into a text file
    [Arguments]    ${pdf_file_name}
    ${text}=    Get Text From Pdf    ${pdf_file_name}
    &{params}=    Create Dictionary    filename=${pdf_file_name}
    Create Session    extract_data_api    http://15422d094df7.ngrok.io/api/v1/
    ${resp}=    Get Request    extract_data_api    /extract_data    params=${params} 
    Should Be Equal As Strings    ${resp.status_code}    200
    Log    ${resp.content}
    ${html_str}=    Decode Bytes To String	${resp.content}    UTF-8
    ${file_html}=    Replace String    ${pdf_file_name}    .pdf    .html 
    ${file_txt}=    Replace String    ${pdf_file_name}    .pdf    .txt  
    Create File    ${TXT_OUTPUT_DIRECTORY_PATH}${file_txt}    overwrite=True
    FOR    ${page}    IN    @{text.keys()}
        Append To File
        ...    ${TXT_OUTPUT_DIRECTORY_PATH}${file_txt}
        ...    ${text[${page}]}
    END
    Create File    ${TXT_OUTPUT_DIRECTORY_PATH}${file_html}    overwrite=True
    Append To File    ${TXT_OUTPUT_DIRECTORY_PATH}${file_html}    ${html_str}

*** Tasks ***
Collecting Search Query From User
    Collect Search Query From User
#${result}=    Collect PDF Files From User
#Extract text from PDF file into a text file    PAVAN.pdf
#Extract text from PDF file into a text file    POORNIMA.pdf
