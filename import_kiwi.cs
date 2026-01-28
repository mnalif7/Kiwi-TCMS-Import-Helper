using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using CsvHelper;
using CsvHelper.Configuration;
using CookComputing.XmlRpc;

namespace KiwiImportOneLine
{
    internal static class Program
    {
        // ====== CONFIG ======
        private const string KIWI_XMLRPC_URL = "http://hub-stg.bosnetdis.com:8000/xml-rpc/";
        private const string USERNAME = "administrator";
        private const string PASSWORD = "QA_Bosn3t";

        private const string CSV_FILE = "kiwi_one_line.csv";
        private const char DELIMITER = ',';           // change to ';' if needed
        private const int DEFAULT_PRIORITY_ID = 1;     // adjust if needed
        private const int DEFAULT_CASE_STATUS_ID = 1;  // 1 = CONFIRMED (commonly), adjust if your server differs
        // ====================

        private static int Main(string[] args)
        {
            int created = 0;
            int failed = 0;

            try
            {
                // Create XML-RPC client
                var kiwi = XmlRpcProxyGen.Create<IKiwiXmlRpc>();
                kiwi.Url = KIWI_XMLRPC_URL;

                // Open CSV (support UTF-8 with BOM like Python "utf-8-sig")
                using var fs = File.OpenRead(CSV_FILE);
                using var sr = new StreamReader(fs, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false), detectEncodingFromByteOrderMarks: true);

                var csvConfig = new CsvConfiguration(CultureInfo.InvariantCulture)
                {
                    Delimiter = DELIMITER.ToString(),
                    HasHeaderRecord = true,
                    BadDataFound = null,
                    MissingFieldFound = null,
                    HeaderValidated = null,
                    IgnoreBlankLines = true,
                    TrimOptions = TrimOptions.Trim,
                };

                using var csv = new CsvReader(sr, csvConfig);

                // Read header
                if (!csv.Read() || !csv.ReadHeader() || csv.HeaderRecord == null)
                {
                    Console.WriteLine("ERROR: CSV has no header.");
                    return 1;
                }

                var headers = new HashSet<string>(
                    csv.HeaderRecord.Select(h => (h ?? "").Trim().ToLowerInvariant())
                );

                var requiredCols = new HashSet<string> { "summary", "product", "category", "steps_text" };
                var missing = requiredCols.Where(r => !headers.Contains(r)).ToArray();
                if (missing.Length > 0)
                {
                    Console.WriteLine($"ERROR: CSV missing columns: {string.Join(", ", missing)}");
                    return 1;
                }

                int lineNumber = 1; // header line = 1

                while (csv.Read())
                {
                    lineNumber++; // data line number

                    // Grab fields by header name
                    var summary = (csv.GetField("summary") ?? "").Trim();
                    if (string.IsNullOrWhiteSpace(summary))
                    {
                        Console.WriteLine($"SKIP line {lineNumber}: empty summary");
                        continue;
                    }

                    var productRaw = (csv.GetField("product") ?? "").Trim();
                    var categoryRaw = (csv.GetField("category") ?? "").Trim();

                    if (!int.TryParse(productRaw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var productId) ||
                        !int.TryParse(categoryRaw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var categoryId))
                    {
                        Console.WriteLine($"FAIL line {lineNumber}: product/category must be integers. summary={summary}");
                        failed++;
                        continue;
                    }

                    var stepsTextRaw = csv.GetField("steps_text") ?? "";
                    var stepsText = CleanText(stepsTextRaw);

                    // Build values like Python dict
                    var values = new XmlRpcStruct
                    {
                        { "summary", summary },
                        { "product", productId },
                        { "category", categoryId },
                        { "priority", DEFAULT_PRIORITY_ID },
                        { "text", stepsText },             // store formatted steps here
                        { "case_status", DEFAULT_CASE_STATUS_ID },
                    };

                    try
                    {
                        // Kiwi server expects auth as first parameter in many installs
                        // (If yours differs, see notes below)
                        var tc = kiwi.TestCaseCreate(USERNAME, PASSWORD, values);

                        // tc is usually a struct/dict with "id"
                        var id = tc.ContainsKey("id") ? tc["id"]?.ToString() : "(no id)";
                        created++;
                        Console.WriteLine($"OK line {lineNumber}: created TestCase id={id} summary={summary}");
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        Console.WriteLine($"FAIL line {lineNumber}: {summary} -> {ex.Message}");
                    }
                }

                Console.WriteLine($"\nDONE. created={created} failed={failed}");
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"FATAL: {ex}");
                return 2;
            }
        }

        private static string CleanText(string? s)
        {
            if (s == null) return "";

            // 1) Convert doubled quotes "" -> "
            s = s.Replace("\"\"", "\"");

            // 2) Remove accidental lone trailing quote at the very end
            s = Regex.Replace(s, "\"\\s*$", "");

            // 3) Normalize CRLF
            s = s.Replace("\r\n", "\n");

            return s.Trim();
        }
    }

    // ===== XML-RPC interface =====
    // Many Kiwi TCMS installs expose methods like "TestCase.create"
    // and accept auth: (username, password, values)
    public interface IKiwiXmlRpc : IXmlRpcProxy
    {
        [XmlRpcMethod("TestCase.create")]
        XmlRpcStruct TestCaseCreate(string username, string password, XmlRpcStruct values);
    }
}